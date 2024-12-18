# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
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
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    List,
    Literal,
    NoReturn,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

from ..hub.api import HubAPI
from ..specs import Job, JobArray, JobGroup, Spec
from .db import Database, Query
from .logger import Logger, MessageLimits
from .summary import Summary
from .types import (
    ApiJob,
    ApiMessage,
    ApiMessagesResponse,
    Attribute,
    ChildEntry,
    JobResult,
    JobState,
    LogEntry,
    LogSeverity,
    Metric,
    MetricScope,
    ProcStat,
)
from .utility import as_couroutine, get_username
from .ws_client import WebsocketClient
from .ws_server import WebsocketServer
from .ws_wrapper import WebsocketWrapper

_TDefault = TypeVar("_TDefault")


class SpecResponse(TypedDict):
    spec: str


GetTreeResponse = Dict[str, Union[str, "GetTreeResponse"]]

HeartbeatCb = Optional[Callable[["BaseLayer", Summary], Union[None, Awaitable[None]]]]


class MetricResponseSuccess(TypedDict):
    result: Literal["success"]


class MetricResponseError(TypedDict):
    result: Literal["error"]
    reason: str


MetricResponse = Union[MetricResponseSuccess, MetricResponseError]


class BaseDatabase(Database):
    async def push_metric(self, metric: Metric):
        pass

    async def push_childentry(self, childentry: ChildEntry):
        pass

    async def push_procstat(self, procstat: ProcStat):
        pass

    async def push_attribute(self, attribute: Attribute):
        pass

    async def push_logentry(self, logentry: LogEntry):
        pass

    async def get_metric(self, **_) -> Any:
        pass

    async def get_childentry(self, **_) -> Any:
        pass

    async def get_procstat(self, **_) -> Any:
        pass

    async def get_attribute(self, **_) -> Any:
        pass

    async def get_logentry(self, **_) -> Any:
        pass

    async def update_metric(self, metric: Metric):
        pass

    async def update_childentry(self, childentry: ChildEntry):
        pass


class Metrics:
    """
    Utility for setting and tracking metrics for different scopes.
    """

    def __init__(self):
        self.raw_metrics: Dict[MetricScope, Dict[str, int]] = DefaultDict(dict)
        self.metrics: Dict[MetricScope, Dict[str, Metric]] = DefaultDict(dict)

    def set(self, scope: MetricScope, name: str, value: int):
        """
        Set metric for given scope
        """
        self.raw_metrics[scope][name] = value

    def set_own(self, name: str, value: int):
        """
        Set metric for own scope
        """
        return self.set(Metric.Scope.OWN, name, value)

    def set_group(self, name: str, value: int):
        """
        Set metric for group scope
        """
        return self.set(Metric.Scope.GROUP, name, value)

    def get(
        self, scope: MetricScope, name: str, default: _TDefault = NoReturn
    ) -> Union[int, _TDefault]:
        """
        Get metric for given scope
        """
        value = self.raw_metrics[scope].get(name, default)
        if value is NoReturn:
            raise KeyError(f"No metric named `{name}` in scope `{scope}`")
        return value

    def get_own(self, name: str, default: _TDefault = NoReturn) -> Union[int, _TDefault]:
        """
        Get metric for own scope
        """
        return self.get(Metric.Scope.OWN, name, default=default)

    def get_group(self, name: str, default: _TDefault = NoReturn) -> Union[int, _TDefault]:
        """
        Get metric for group scope
        """
        return self.get(Metric.Scope.GROUP, name, default=default)

    def dump(self, scope: MetricScope) -> Dict[str, int]:
        """
        Dump given scope to dict
        """
        return self.raw_metrics[scope].copy()

    def dump_own(self) -> Dict[str, int]:
        """
        Dump own scope to dict
        """
        return self.dump(Metric.Scope.OWN)

    def dump_group(self) -> Dict[str, int]:
        """
        Dump group scope to dict
        """
        return self.dump(Metric.Scope.GROUP)

    async def sync(self, db: BaseDatabase):
        """
        Sync values to the provided database
        """
        for scope, name_values in self.raw_metrics.items():
            for name, value in name_values.items():
                if (metric := self.metrics[scope].get(name, None)) is not None:
                    metric.value = value
                    await db.update_metric(metric)
                else:
                    await db.push_metric(metric := Metric(scope=scope, name=name, value=value))
                    self.metrics[scope][name] = metric


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
        heartbeat_cb: Optional[HeartbeatCb] = None,
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
        self.heartbeat_cb = None if heartbeat_cb is None else as_couroutine(heartbeat_cb)
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
        self.metrics = Metrics()
        self.started: Optional[float] = None
        self.updated: Optional[float] = None
        self.stopped: Optional[float] = None
        self.result: JobResult = JobResult.UNKNOWN

    @property
    def server(self) -> WebsocketServer:
        if (value := getattr(self, "__server", None)) is None:
            raise AttributeError("Server not set yet!")
        return value

    @server.setter
    def server(self, value: WebsocketServer):
        setattr(self, "__server", value)

    @property
    def client(self) -> WebsocketClient:
        if (value := getattr(self, "__client", None)) is None:
            raise AttributeError("Client not set yet!")
        return value

    @client.setter
    def client(self, value: WebsocketClient):
        setattr(self, "__client", value)

    @property
    def db(self) -> BaseDatabase:
        if (value := getattr(self, "__db", None)) is None:
            raise AttributeError("db not set yet!")
        return value

    @db.setter
    def db(self, value: Database):
        setattr(self, "__db", value)

    async def setup(self, *args: List[Any], **kwargs: Dict[str, Any]) -> None:
        # Set initial metrics
        self.metrics.set_own("sub_total", 1)
        self.metrics.set_own("sub_active", 1)
        self.metrics.set_own("sub_passed", 0)
        self.metrics.set_own("sub_failed", 0)
        # Ensure the tracking directory exists
        self.tracking.mkdir(exist_ok=True, parents=True)
        # Dump the spec into the tracking directory
        (self.tracking / "spec.yaml").write_text(Spec.dump(self.spec))
        # Create a local database
        self.db = Database(self.tracking / "db.sqlite")
        await self.db.start()
        await self.db.register(Metric)
        await self.db.register(Attribute)
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
            result = await self.client.register(ident=self.ident, server=server_address)
            self.uidx = int(result["uidx"])
            self.root = int(result["root"])
            self.path = result["path"]
        # Otherwise, register with the parent
        else:
            self.__hub_uid = await HubAPI.register(
                ident=self.ident,
                url=server_address,
                layer=type(self).__name__.lower(),
                owner=get_username(),
            )
            if self.__hub_uid is not None:
                self.uidx = self.root = int(self.__hub_uid)
                self.path = []
                await self.logger.info(f"Registered with hub with ID {self.__hub_uid}")
            else:
                self.uidx = self.root = 0
                self.path = []
        # Setup basic job info
        await self.db.push_attribute(Attribute(name="ident", value=self.ident))
        await self.db.push_attribute(Attribute(name="uidx", value=str(self.uidx)))
        await self.db.push_attribute(Attribute(name="root", value=str(self.root)))
        await self.db.push_attribute(Attribute(name="path", value=".".join(self.path)))
        # Schedule the heartbeat
        self.__hb_event = asyncio.Event()
        self.__hb_task = asyncio.create_task(self.__heartbeat_loop(self.__hb_event))

    async def teardown(self, *args: List[Any], **kwargs: Dict[str, Any]) -> None:
        # Stop the heartbeat process
        self.__hb_event.set()
        await asyncio.wait_for(self.__hb_task, timeout=(2 * self.interval))
        # Get job status and set relevant attributes
        msg_ok = await self.logger.check_limits(self.limits)
        code_ok = self.code == 0
        tree_ok = self.metrics.get_group("sub_failed") == 0
        if code_ok and msg_ok and tree_ok:
            assert self.result != JobResult.FAILURE, "Went from a failing to passing state!?"
            self.result = JobResult.SUCCESS
            self.metrics.set_own("sub_passed", 1)
            self.metrics.set_own("sub_failed", 0)
        else:
            self.result = JobResult.FAILURE
            self.metrics.set_own("sub_passed", 0)
            self.metrics.set_own("sub_failed", 1)
            if not code_ok:
                await self.logger.error("Job failed as it violated the message limit")
            if not msg_ok:
                await self.logger.error(f"Job failed with exit code {self.code}")
            if not tree_ok:
                await self.logger.error("Job failed because a child failed")
        self.metrics.set_own("sub_active", 0)
        # Record result in own db
        await self.db.push_attribute(Attribute(name="result", value=str(self.result)))
        # Tell the parent the job is complete
        summary = await self.heartbeat()
        if self.heartbeat_cb:
            # Callback with final status
            await self.heartbeat_cb(self, summary)
        await self.client.complete(
            ident=self.ident, code=self.code, result=self.result, summary=summary.as_dict()
        )
        # Log the warning/error count
        msg_keys = [f"msg_{x.name.lower()}" for x in LogSeverity]
        parts = []
        for name, value in self.metrics.dump_own().items():
            if name in msg_keys:
                parts.append(f"{value} {name.split('msg_')[1]}")
        await self.logger.info("Recorded " + ", ".join(parts[:-1]) + f" and {parts[-1]} messages")
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()
        # Notify the hub of completion
        if self.__hub_uid is not None:
            await HubAPI.complete(
                uid=self.__hub_uid, db_file=self.db.path.as_posix(), result=self.result
            )
            await HubAPI.stop()

    async def stop(self, **kwargs) -> None:
        self.terminated = True

    async def __heartbeat_loop(self, done_evt: asyncio.Event) -> None:
        try:
            # NOTE: We don't loop on done_evt so that there is always a final
            #       pass after completion
            while True:
                # Run the heartbeat process
                summary = await self.heartbeat()
                # If a heartbeat callback is registered, deliver the result
                if self.heartbeat_cb:
                    await self.heartbeat_cb(self, summary)
                # If linked, update hub with heartbeat data
                if self.__hub_uid is not None:
                    await HubAPI.heartbeat(self.__hub_uid, summary)
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
        # Update own metrics
        for sev in LogSeverity:
            self.metrics.set_own(f"msg_{sev.name.lower()}", self.logger.get_count(sev))
        self.updated = datetime.now().timestamp()
        msg_ok = await self.logger.check_limits(self.limits)
        if not msg_ok:
            self.result = JobResult.FAILURE
        # Summarise state
        summary = await self.summarise()
        # Update group metrics
        for name, value in summary.metrics.items():
            self.metrics.set_group(name, value)
        # Sync metrics to database
        await self.metrics.sync(self.db)
        # Report to parent
        await self.client.update(ident=self.ident, summary=summary.as_dict(), result=self.result)
        # Return the summary
        return summary

    async def get_messages(
        self, ws: WebsocketWrapper, after: int = 0, limit: int = 10
    ) -> ApiMessagesResponse:
        msgs: List[LogEntry] = await self.db.get_logentry(
            sql_order_by=("db_uid", True),
            sql_limit=limit,
            db_uid=Query(gt=after),
        )
        total: int = await self.db.get_logentry(sql_count=True)
        messages: list[ApiMessage] = [
            ApiMessage(
                uid=x.db_uid,
                severity=int(x.severity),
                message=x.message,
                timestamp=int(x.timestamp.timestamp()),
            )
            for x in msgs
        ]
        return {"messages": messages, "total": total, "status": JobState.STARTED}

    async def resolve(
        self, root_path: List[str], nest_path: Optional[List[str]] = None, depth: int = 0, **_
    ) -> ApiJob:
        del root_path, nest_path, depth
        return ApiJob(
            uidx=self.uidx,
            root=self.root,
            path=self.path,
            ident=self.ident,
            status=JobState.STARTED,
            metrics=self.metrics.dump_group(),
            server_url=await self.server.get_address(),
            db_file=self.db.path.as_posix(),
            owner=None,
            started=self.started,
            updated=self.updated,
            stopped=self.stopped,
            result=self.result,
            children=[],
            expected_children=0,
        )

    @property
    def ident(self) -> str:
        return self.spec.ident or str(os.getpid())

    @property
    def is_root(self) -> bool:
        return (self.client is None) or (not self.client.linked)

    async def summarise(self) -> Summary:
        return Summary(
            metrics=self.metrics.dump_own(),
        )
