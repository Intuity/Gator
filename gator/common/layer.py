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
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, Union

from ..hub.api import HubAPI
from ..specs import Job, JobArray, JobGroup, Spec
from .db import Database, Query
from .logger import Logger, MessageLimits
from .summary import Summary, make_summary
from .types import Attribute, LogEntry, LogSeverity, Metric, ProcStat, Result
from .utility import get_username
from .ws_client import WebsocketClient
from .ws_server import WebsocketServer
from .ws_wrapper import WebsocketWrapper


class ResolveResponse(TypedDict):
    ident: str
    server_url: str
    metrics: Dict[str, int]


class Message(TypedDict):
    uid: int
    severity: int
    message: str
    timestamp: int


class SpecResponse(TypedDict):
    spec: str


class GetMessagesResponse(TypedDict):
    messages: List[Message]
    total: int


GetTreeResponse = Dict[str, Union[str, "GetTreeResponse"]]


class MetricResponseSuccess(TypedDict):
    result: Literal["success"]


class MetricResponseError(TypedDict):
    result: Literal["error"]
    reason: str


MetricResponse = Union[MetricResponseSuccess, MetricResponseError]


class ChildResponseData(TypedDict):
    state: str
    result: str
    server: str
    exitcode: int
    summary: Summary
    started: int
    updated: int
    completed: int


ChildrenResponse = List[ChildResponseData]


def null(*args, **kwargs):
    ...


class _BaseServer(WebsocketServer):
    async def get_messages(self, after: int, limit: int) -> GetMessagesResponse:
        ...

    async def resolve(self, path: List[str]) -> ResolveResponse:
        ...

    async def metric(self, name: str, value: int) -> MetricResponse:
        ...


class _BaseClient(WebsocketClient):
    async def stop(self):
        ...

    async def resolve(self, path: List[str]) -> ResolveResponse:
        ...

    async def update(self, ident: str, summary: Summary):
        ...

    async def complete(self, ident: str, result: str, code: int, summary: Summary):
        ...

    async def children(self) -> ChildrenResponse:
        ...

    async def spec(self, ident: str) -> SpecResponse:
        ...

    async def get_tree(self) -> GetTreeResponse:
        ...


class _BaseDatabase(Database):
    async def push_metric(self, metric: Metric):
        ...

    async def push_procstat(self, procstat: ProcStat):
        ...

    async def push_attribute(self, attribute: Attribute):
        ...

    async def push_logentry(self, logentry: LogEntry):
        ...

    async def get_metric(self, **_) -> Any:
        ...

    async def get_procstat(self, **_) -> Any:
        ...

    async def get_attribute(self, **_) -> Any:
        ...

    async def get_logentry(self, **_) -> Any:
        ...

    async def update_metric(self, metric: Metric):
        ...


class BaseLayer:
    """Shared behaviours for all layers in the job tree"""

    def __init__(
        self,
        spec: Union[Job, JobArray, JobGroup],
        logger: Logger,
        client: Optional[WebsocketClient] = None,
        tracking: Optional[Path] = None,
        interval: int = 5,
        quiet: bool = False,
        all_msg: bool = False,
        heartbeat_cb: Optional[Callable] = None,
        limits: MessageLimits = None,
    ) -> None:
        # Capture initialisation variables
        self.spec = spec
        if client:
            self.client = client
        self.logger = logger
        # Set the default tracking path
        self.tracking = (Path.cwd() / "tracking") if tracking is None else tracking
        self.interval = interval
        self.quiet = quiet
        self.all_msg = all_msg
        self.heartbeat_cb = heartbeat_cb
        self.limits = limits or MessageLimits()
        # Check spec object
        self.spec.check()
        # Create empty pointers in advance
        self.code = 0
        self.__hub_uid = None
        self.__hb_event = None
        self.__hb_task = None
        # State
        self.complete = False
        self.terminated = False
        self.metrics = {}

    @property
    def server(self) -> _BaseServer:
        if (value := getattr(self, "__server", None)) is None:
            raise AttributeError("Server not set yet!")
        return value

    @server.setter
    def server(self, value: WebsocketServer):
        setattr(self, "__server", value)

    @property
    def client(self) -> _BaseClient:
        if (value := getattr(self, "__client", None)) is None:
            raise AttributeError("Client not set yet!")
        return value

    @client.setter
    def client(self, value: WebsocketClient):
        setattr(self, "__client", value)

    @property
    def db(self) -> _BaseDatabase:
        if (value := getattr(self, "__db", None)) is None:
            raise AttributeError("db not set yet!")
        return value

    @db.setter
    def db(self, value: Database):
        setattr(self, "__db", value)

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
            await self.db.push_metric(metric := Metric(name=f"msg_{sev.name.lower()}", value=0))
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
        assert self.client is not None, "Client is not set?"
        self.client.add_route("stop", self.stop)
        self.client.add_route("resolve", self.resolve)
        # If linked, ping and then register with the parent
        if self.client.linked:
            await self.client.measure_latency()
            await self.client.register(ident=self.ident, server=server_address)
        # Otherwise, register with the parent
        else:
            self.__hub_uid = await HubAPI.register(
                ident=self.ident,
                url=server_address,
                layer=type(self).__name__.lower(),
                owner=get_username(),
            )
            if self.__hub_uid is not None:
                await self.logger.info(f"Registered with hub with ID {self.__hub_uid}")
        # Schedule the heartbeat
        self.__hb_event = asyncio.Event()
        self.__hb_task = asyncio.create_task(self.__heartbeat_loop(self.__hb_event))

    async def teardown(self, *args: List[Any], **kwargs: Dict[str, Any]) -> None:
        # Stop the heartbeat process
        self.__hb_event.set()
        await asyncio.wait_for(self.__hb_task, timeout=(2 * self.interval))
        # Determine the result
        result = Result.SUCCESS
        if not (await self.logger.check_limits(self.limits)):
            await self.logger.error("Job failed as it violated the message limit")
            result = Result.FAILURE
        # Tell the parent the job is complete
        summary = await self.summarise()
        await self.client.complete(
            ident=self.ident, code=self.code, result=result.name, summary=summary
        )
        # Log the warning/error count
        msg_keys = [f"msg_{x.name.lower()}" for x in LogSeverity]
        msg_metrics = filter(lambda x: x.name in msg_keys, self.metrics.values())
        parts = [f"{x.value} {x.name.split('msg_')[1]}" for x in msg_metrics]
        await self.logger.info("Recorded " + ", ".join(parts[:-1]) + f" and {parts[-1]} messages")
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()
        # Notify the hub of completion
        if self.__hub_uid is not None:
            await HubAPI.complete(uid=self.__hub_uid, db_file=self.db.path.as_posix())
            await HubAPI.stop()

    async def stop(self, **kwargs) -> None:
        self.terminated = True

    async def __heartbeat_loop(self, done_evt: asyncio.Event) -> None:
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

    async def heartbeat(self) -> Summary:
        # Update logging metrics
        for sev in LogSeverity:
            metric = self.metrics[f"msg_{sev.name.lower()}"]
            metric.value = self.logger.get_count(sev)
            await self.db.update_metric(metric)
        # Summarise state
        summary = await self.summarise()
        # Report to parent
        await self.client.update(ident=self.ident, summary=summary)
        # Return the summary
        return summary

    async def get_messages(
        self, ws: WebsocketWrapper, after: int = 0, limit: int = 10
    ) -> GetMessagesResponse:
        msgs: List[LogEntry] = await self.db.get_logentry(
            sql_order_by=("db_uid", True),
            sql_limit=limit,
            db_uid=Query(gte=after),
        )
        total: int = await self.db.get_logentry(sql_count=True)
        messages: list[Message] = [
            Message(
                uid=x.db_uid,
                severity=int(x.severity),
                message=x.message,
                timestamp=int(x.timestamp.timestamp()),
            )
            for x in msgs
        ]
        return {"messages": messages, "total": total}

    async def resolve(self, path: List[str], **_) -> ResolveResponse:
        del path
        return {
            "ident": self.ident,
            "server_url": await self.server.get_address(),
            "metrics": (await self.summarise()).get("metrics", {}),
        }

    @property
    def ident(self) -> str:
        return self.spec.ident or str(os.getpid())

    @property
    def is_root(self) -> bool:
        return (self.client is None) or (not self.client.linked)

    async def summarise(self) -> Summary:
        return make_summary(
            metrics={k: x.value for k, x in self.metrics.items()},
        )
