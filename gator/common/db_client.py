from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, cast

from .db import Database, Query
from .layer import (
    BaseDatabase,
    DeadResolveResponse,
    GetMessagesResponse,
    GetTreeResponse,
    Message,
    ResolveResponse,
)
from .types import Attribute, ChildEntry, LogEntry, Metric
from .ws_client import WebsocketClient


@asynccontextmanager
async def resolve_client(server_url: str, db_file: str | None):
    try:
        if db_file is None:
            async with downstream_client(server_url) as ws:
                yield ws
        else:
            async with database_client(db_file) as ws:
                yield ws
    finally:
        pass


class _DBClient:
    def __init__(self, db: BaseDatabase):
        self.db = db

    async def resolve(self, path: List[str]) -> ResolveResponse:
        children = {
            child.ident: {"server_url": child.server_url, "db_file": child.db_file}
            for child in await self.db.get_childentry()
        }

        if path:
            child_ident = path[0]
            db_file = children[child_ident]["db_file"]
            async with database_client(db_file) as db:
                return await db.resolve(path[1:])

        ident = (await self.db.get_attribute(name="ident"))[0].value

        metrics = {metric.name: metric.value for metric in await self.db.get_metric()}

        return DeadResolveResponse(
            ident=ident,
            server_url=None,
            db_file=self.db.path.as_posix(),
            children=children,
            metrics=metrics,
            live=False,
        )

    async def get_messages(self, after: int = 0, limit: int = 10) -> GetMessagesResponse:
        msgs: List[LogEntry] = await self.db.get_logentry(
            sql_order_by=("db_uid", True),
            sql_limit=limit,
            db_uid=Query(gt=after),
        )
        total: int = await self.db.get_logentry(sql_count=True)
        messages: list[Message] = [
            Message(
                uid=cast(int, x.db_uid),
                severity=int(x.severity),
                message=x.message,
                timestamp=int(x.timestamp.timestamp()),
            )
            for x in msgs
        ]
        return {"messages": messages, "total": total, "live": False}

    async def get_tree(self) -> GetTreeResponse:
        raise NotImplementedError("get_tree")


class _WSClient:
    def __init__(self, ws: WebsocketClient):
        self.ws = ws

    async def resolve(self, path: List[str]) -> ResolveResponse:
        return await self.ws.resolve(path=path)

    async def get_messages(self, after: int = 0, limit: int = 10) -> GetMessagesResponse:
        return await self.ws.get_messages(after=after, limit=limit)

    async def get_tree(self) -> GetTreeResponse:
        raise NotImplementedError("get_tree")


@asynccontextmanager
async def database_client(path: str | Path):
    if not Path(path).exists():
        raise RuntimeError("No Exist")
    db = Database(Path(path))
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
