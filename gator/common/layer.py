# Copyright 2023, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .ws_client import WebsocketClient
from .db import Database, Query
from .logger import Logger
from .ws_server import WebsocketServer
from ..specs import Job, JobArray, JobGroup
from .types import LogEntry, LogSeverity


class BaseLayer:
    """ Shared behaviours for all layers in the job tree """

    def __init__(self,
                 spec         : Union[Job, JobArray, JobGroup],
                 client       : Optional[WebsocketClient] = None,
                 logger       : Optional[Logger] = None,
                 tracking     : Path = Path.cwd() / "tracking",
                 interval     : int = 5,
                 quiet        : bool = False,
                 all_msg      : bool = False,
                 heartbeat_cb : Optional[Callable] = None) -> None:
        # Capture initialisation variables
        self.spec         = spec
        self.client       = client
        self.logger       = logger
        self.tracking     = tracking
        self.interval     = interval
        self.quiet        = quiet
        self.all_msg      = all_msg
        self.heartbeat_cb = heartbeat_cb
        # Check spec object
        self.spec.check()
        # Create empty pointers in advance
        self.code       = 0
        self.db         = None
        self.server     = None
        self.__hb_event = None
        self.__hb_task  = None
        # State
        self.complete   = False
        self.terminated = False

    async def setup(self,
                    *args    : List[Any],
                    **kwargs : Dict[str, Any]) -> None:
        # Create a local database
        self.db = Database(self.tracking / "db.sqlite")
        async def _log_cb(entry : LogEntry) -> None:
            await self.logger.log(entry.severity, entry.message)
        await self.db.start()
        self.db.define_transform(LogSeverity, "INTEGER", int, LogSeverity)
        await self.db.register(LogEntry, None if self.quiet else _log_cb)
        # Setup server
        self.server    = WebsocketServer(db=self.db)
        server_address = await self.server.start()
        # Add handlers for downwards calls
        self.client.add_route("stop", self.stop)
        # If linked, ping the parent
        if self.client.linked:
            await self.client.measure_latency()
        # Register with the parent
        await self.client.register(id=self.id, server=server_address)
        # Schedule the heartbeat
        self.__hb_event = asyncio.Event()
        self.__hb_task  = asyncio.create_task(self.__heartbeat_loop(self.__hb_event))

    async def teardown(self,
                       *args    : List[Any],
                       **kwargs : Dict[str, Any]) -> None:
        # Stop the heartbeat process
        self.__hb_event.set()
        await asyncio.wait_for(self.__hb_task, timeout=(2 * self.interval))
        # Tell the parent the job is complete
        summary = await self.summarise()
        await self.client.complete(id  =self.id,
                                   code=self.code,
                                   **summary)
        # Log the warning/error count
        num_wrn = summary.get("warnings", 0)
        num_err = summary.get("errors",   0)
        await self.logger.info(f"Recorded {num_wrn} warnings and {num_err} errors")
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()

    async def stop(self, **kwargs) -> None:
        self.terminated = True

    async def __heartbeat_loop(self, done_evt : asyncio.Event) -> None:
        cb_async = self.heartbeat_cb and asyncio.iscoroutinefunction(self.heartbeat_cb)
        try:
            # NOTE: We don't loop on done_evt so that there is always a final
            #       pass after completion
            while True:
                # Run the heartbeat process
                result = await self.heartbeat()
                # If a heartbeat callback is registered, deliver the result
                if self.heartbeat_cb:
                    call = self.heartbeat_cb(self, **result)
                    if cb_async:
                        await call
                # If done event set, break out
                if done_evt.is_set():
                    break
                # Wait for the next interval
                try:
                    await asyncio.wait_for(done_evt.wait(), self.interval)
                except asyncio.exceptions.TimeoutError:
                    pass
        except asyncio.exceptions.CancelledError:
            pass

    async def heartbeat(self) -> None:
        # Summarise state
        summary = await self.summarise()
        # Report to parent
        await self.client.update(id=self.id, **summary)
        # Return the summary
        return summary

    @property
    def id(self) -> str:
        return self.spec.id or str(os.getpid())

    @property
    def is_root(self) -> bool:
        return (self.client is None) or (not self.client.linked)

    async def summarise(self) -> Dict[str, int]:
        wrn_count = await self.db.get_logentry(sql_count=True, severity=LogSeverity.WARNING)
        err_count = await self.db.get_logentry(sql_count=True, severity=Query(gte=LogSeverity.ERROR))
        return { "warnings": wrn_count, "errors": err_count }
