from contextlib import asynccontextmanager
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, cast

from .child import Child
from .db import Database, Query
from .layer import (
    BaseDatabase,
    GetTreeResponse,
)
from .types import (
    ApiMessage,
    ApiMessagesResponse,
    ApiResolvable,
    ApiTreeResponse,
    Attribute,
    ChildEntry,
    JobResult,
    JobState,
    LogEntry,
    Metric,
)
from .ws_client import WebsocketClient
from .ws_wrapper import WebsocketWrapper


@asynccontextmanager
async def resolve_client(job: ApiResolvable):
    try:
        if job["status"] == JobState.STARTED:
            async with downstream_client(job["server_url"]) as ws:
                yield ws
        elif job["status"] == JobState.COMPLETE:
            async with database_client(job["db_file"]) as ws:
                yield ws
        else:
            raise RuntimeError(f"Can't resolve job {job}")
    finally:
        pass


class _DBClient:
    def __init__(self, db: BaseDatabase):
        self.db = db

    async def resolve(
        self, root_path: List[str], nest_path: Optional[List[str]] = None, depth: int = 0
    ):
        children: List[ChildEntry] = []
        if self.db.has_table(ChildEntry):
            children = await self.db.get_childentry()
        elif resolve_path := (root_path or nest_path):
            raise RuntimeError(f"Tried to resolve `{resolve_path[0]}` in db without child entries")

        # Tunnl down to root
        if root_path:
            resolve_ident = root_path[0]
            for child in children:
                if child.ident == resolve_ident:
                    async with database_client(child.db_file) as db:
                        return await db.resolve(
                            root_path=root_path[1:], nest_path=nest_path, depth=depth
                        )
            else:
                raise RuntimeError(f"Couldn't find child with ident `{resolve_ident}`")

        # Resolve self
        ident = (await self.db.get_attribute(name="ident"))[0].value
        uidx = (await self.db.get_attribute(name="uidx"))[0].value

        started_attr = await self.db.get_attribute(name="started")
        stopped_attr = await self.db.get_attribute(name="stopped")
        result_attr = await self.db.get_attribute(name="result")
        start = started_attr[0].value if started_attr else None
        stop = stopped_attr[0].value if stopped_attr else None
        result = JobResult(int(result_attr[0].value)) if result_attr else JobResult.UNKNOWN

        metrics: Dict[str, int] = {}
        child_metrics: Dict[str, Dict[str, int]] = DefaultDict(dict)
        for metric in await self.db.get_metric():
            if metric.scope == Metric.Scope.GROUP:
                metrics[metric.name] = metric.value
            elif metric.scope == Metric.Scope.OWN:
                pass
            else:
                child_metrics[metric.scope][metric.name] = metric.value

        # Resolve nested path
        jobs: List[ApiTreeResponse] = []
        if nest_path:
            resolve_ident = nest_path[0]
            for child in children:
                if child.ident == resolve_ident:
                    async with database_client(child.db_file) as db:
                        jobs.append(
                            await db.resolve(root_path=[], nest_path=nest_path[1:], depth=depth)
                        )
                        break
            else:
                raise RuntimeError(f"Couldn't find child with ident `{resolve_ident}`")
        elif depth > 1:
            for child in children:
                async with database_client(child.db_file) as db:
                    jobs.append(await db.resolve(root_path=[], nest_path=[], depth=depth - 1))
        elif depth == 1:
            for child in children:
                jobs.append(
                    ApiTreeResponse(
                        uidx=child.db_uid,
                        ident=child.ident,
                        status=JobState.COMPLETE,
                        metrics=child_metrics[child.ident],
                        server_url=child.server_url,
                        db_file=child.db_file,
                        owner=None,
                        result=JobResult(int(child.result)),
                        started=child.started,
                        updated=child.updated,
                        stopped=child.stopped,
                        expected_children=child.expected_children,
                        jobs=[],
                    )
                )

        return ApiTreeResponse(
            uidx=uidx,
            ident=ident,
            status=JobState.COMPLETE,
            metrics=metrics,
            server_url="",
            db_file=self.db.path.as_posix(),
            started=start,
            updated=stop or start,
            stopped=stop,
            owner=None,
            result=result,
            jobs=jobs,
            expected_children=len(jobs),
        )

    async def get_messages(self, after: int = 0, limit: int = 10) -> ApiMessagesResponse:
        msgs: List[LogEntry] = await self.db.get_logentry(
            sql_order_by=("db_uid", True),
            sql_limit=limit,
            db_uid=Query(gt=after),
        )
        total: int = await self.db.get_logentry(sql_count=True)
        messages: list[ApiMessage] = [
            ApiMessage(
                uid=cast(int, x.db_uid),
                severity=int(x.severity),
                message=x.message,
                timestamp=int(x.timestamp.timestamp()),
            )
            for x in msgs
        ]
        return {"messages": messages, "total": total, "status": JobState.COMPLETE}

    async def get_tree(self) -> GetTreeResponse:
        raise NotImplementedError("get_tree")


class _WSClient:
    def __init__(self, ws: WebsocketClient | WebsocketWrapper):
        self.ws = ws

    async def resolve(
        self, root_path: List[str], nest_path: Optional[List[str]] = None, depth: int = 0
    ) -> ApiTreeResponse:
        return await self.ws.resolve(root_path=root_path, nest_path=nest_path, depth=depth)

    async def get_messages(self, after: int = 0, limit: int = 10) -> ApiMessagesResponse:
        return await self.ws.get_messages(after=after, limit=limit)

    async def get_tree(self) -> GetTreeResponse:
        raise NotImplementedError("get_tree")


@asynccontextmanager
async def database_client(path: str | Path):
    path = Path(path)
    if not path.exists():
        raise RuntimeError("No Exist")
    db = Database(path, readonly=True)
    try:
        await db.start()
        await db.register(Metric)
        await db.register(Attribute)
        await db.register(ChildEntry)
        await db.register(LogEntry)
        yield _DBClient(cast(BaseDatabase, db))
    finally:
        await db.stop()


@asynccontextmanager
async def downstream_client(server_url: str):
    try:
        async with WebsocketClient(server_url) as ws:
            yield _WSClient(ws)
    finally:
        pass


@asynccontextmanager
async def websocket_client(websocket: WebsocketWrapper):
    try:
        yield _WSClient(websocket)
    finally:
        pass


@asynccontextmanager
async def child_client(child: Child):
    match child.state:
        case JobState.PENDING | JobState.LAUNCHED:
            client = None
        case JobState.COMPLETE:
            client = database_client(path=child.tracking / "db.sqlite")
        case JobState.STARTED:
            assert child.ws is not None, "Child started but no websocket!"
            client = websocket_client(child.ws)
    try:
        if client is None:
            yield None
        else:
            async with client as cli:
                yield cli
    finally:
        pass
