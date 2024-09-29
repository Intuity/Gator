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

from ..hub.api import HubAPI
from ..specs import Job, JobArray, JobGroup, Spec
from .db import Database, Query
from .logger import Logger, MessageLimits
from .types import LogEntry, LogSeverity, Metric, Result
from .utility import get_username
from .ws_client import WebsocketClient
from .ws_server import WebsocketServer
from .ws_wrapper import WebsocketWrapper


class BaseLayer:
    """Shared behaviours for all layers in the job tree"""

    def __init__(
        self,
        spec: Union[Job, JobArray, JobGroup],
        client: Optional[WebsocketClient] = None,
        logger: Optional[Logger] = None,
        tracking: Path = Path.cwd() / "tracking",
        interval: int = 5,
        quiet: bool = False,
        all_msg: bool = False,
        heartbeat_cb: Optional[Callable] = None,
        limits: MessageLimits = None,
    ) -> None:
        # Capture initialisation variables
        self.spec = spec
        self.client = client
        self.logger = logger
        self.tracking = tracking
        self.interval = interval
        self.quiet = quiet
        self.all_msg = all_msg
        self.heartbeat_cb = heartbeat_cb
        self.limits = limits or MessageLimits()
        # Check spec object
        self.spec.check()
        # Create empty pointers in advance
        self.code = 0
        self.db = None
        self.server = None
        self.__hub_uid = None
        self.__hb_event = None
        self.__hb_task = None
        # State
        self.complete = False
        self.terminated = False
        self.metrics = {}

    async def setup(self, *args: List[Any], **kwargs: Dict[str, Any]) -> None:
        # Ensure the tracking directory exists
        self.tracking.mkdir(exist_ok=True, parents=True)
        # Dump the spec into the tracking directory
        (self.tracking / "spec.yaml").write_text(Spec.dump(self.spec))
        # Create a local database
        self.db = Database(self.tracking / "db.sqlite")
        await self.db.start()
        await self.db.register(Metric)
        # Setup base metrics
        for sev in LogSeverity:
            await self.db.push_metric(
                metric := Metric(name=f"msg_{sev.name.lower()}", value=0)
            )
            self.metrics[metric.name] = metric
        # Setup logger
        await self.logger.set_database(self.db)
        self.logger.tee_to_file(self.tracking / "messages.log")
        # Setup server
        self.server = WebsocketServer(db=self.db, logger=self.logger)
        server_address = await self.server.start()
        self.server.add_route("get_messages", self.get_messages)
        self.server.add_route("resolve", self.resolve)
        # Add handlers for downwards calls
        self.client.add_route("stop", self.stop)
        self.client.add_route("resolve", self.resolve)
        # If linked, ping and then register with the parent
        if self.client.linked:
            await self.client.measure_latency()
            await self.client.register(id=self.id, server=server_address)
        # Otherwise, register with the parent
        else:
            self.__hub_uid = await HubAPI.register(
                id=self.id,
                url=server_address,
                layer=type(self).__name__.lower(),
                owner=get_username(),
            )
            if self.__hub_uid is not None:
                await self.logger.info(
                    f"Registered with hub with ID {self.__hub_uid}"
                )
        # Schedule the heartbeat
        self.__hb_event = asyncio.Event()
        self.__hb_task = asyncio.create_task(
            self.__heartbeat_loop(self.__hb_event)
        )

    async def teardown(
        self, *args: List[Any], **kwargs: Dict[str, Any]
    ) -> None:
        # Stop the heartbeat process
        self.__hb_event.set()
        await asyncio.wait_for(self.__hb_task, timeout=(2 * self.interval))
        # Determine the result
        result = Result.SUCCESS
        if not (await self.logger.check_limits(self.limits)):
            await self.logger.error(
                "Job failed as it violated the message limit"
            )
            result = Result.FAILURE
        # Tell the parent the job is complete
        summary = await self.summarise()
        await self.client.complete(
            id=self.id, code=self.code, result=result.name, **summary
        )
        # Log the warning/error count
        msg_keys = [f"msg_{x.name.lower()}" for x in LogSeverity]
        msg_metrics = filter(
            lambda x: x.name in msg_keys, self.metrics.values()
        )
        parts = [f"{x.value} {x.name.split('msg_')[1]}" for x in msg_metrics]
        await self.logger.info(
            "Recorded " + ", ".join(parts[:-1]) + f" and {parts[-1]} messages"
        )
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()
        # Notify the hub of completion
        if self.__hub_uid is not None:
            await HubAPI.complete(
                uid=self.__hub_uid, db_file=self.db.path.as_posix()
            )
            await HubAPI.stop()

    async def stop(self, **kwargs) -> None:
        self.terminated = True

    async def __heartbeat_loop(self, done_evt: asyncio.Event) -> None:
        cb_async = self.heartbeat_cb and asyncio.iscoroutinefunction(
            self.heartbeat_cb
        )
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
                # If linked, update hub with heartbeat data
                if self.__hub_uid is not None:
                    await HubAPI.heartbeat(self.__hub_uid, result)
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

    async def heartbeat(self) -> Dict[str, int]:
        # Update logging metrics
        for sev in LogSeverity:
            metric = self.metrics[f"msg_{sev.name.lower()}"]
            metric.value = self.logger.get_count(sev)
            await self.db.update_metric(metric)
        # Summarise state
        summary = await self.summarise()
        # Report to parent
        await self.client.update(id=self.id, **summary)
        # Return the summary
        return summary

    async def get_messages(
        self, ws: WebsocketWrapper, after: int = 0, limit: int = 10
    ) -> List[Dict[str, Union[str, int]]]:
        msgs: List[LogEntry] = await self.db.get_logentry(
            sql_order_by=("db_uid", True),
            sql_limit=limit,
            db_uid=Query(gte=after),
        )
        total: int = await self.db.get_logentry(sql_count=True)
        format = [
            {
                "uid": x.db_uid,
                "severity": int(x.severity),
                "message": x.message,
                "timestamp": int(x.timestamp.timestamp()),
            }
            for x in msgs
        ]
        return {"messages": format, "total": total}

    async def resolve(self, path: List[str], **_) -> None:
        del path
        return {
            "id": self.id,
            "server_url": await self.server.get_address(),
            "metrics": (await self.summarise()).get("metrics", {}),
        }

    @property
    def id(self) -> str:
        return self.spec.id or str(os.getpid())

    @property
    def is_root(self) -> bool:
        return (self.client is None) or (not self.client.linked)

    async def summarise(self) -> Dict[str, int]:
        return {"metrics": {k: x.value for k, x in self.metrics.items()}}
