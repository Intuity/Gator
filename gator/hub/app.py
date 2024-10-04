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

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Union

from quart import (
    Quart,
    current_app,
    request,
)

from ..common.ws_client import WebsocketClient
from .tables import setup_db


def setup_hub(
    host: str,
    port: int,
    static: Path,
    db_host: str,
    db_port: str,
    db_name: str,
    db_user: str,
    db_pwd: str,
):
    # Setup database
    db, tables = setup_db(db_host, db_port, db_name, db_user, db_pwd)

    # Create Quart application to host the interface and handle API requests
    hub = Quart(
        "gator-hub",
        static_folder=static.as_posix(),
        static_url_path="",
    )

    @hub.before_serving
    async def start_database():
        nonlocal db
        await db.start_connection_pool()
        await tables.Completion.create_table(if_not_exists=True)
        await tables.Registration.create_table(if_not_exists=True)
        await tables.Metric.create_table(if_not_exists=True)

    @hub.after_serving
    async def stop_database():
        nonlocal db
        await db.close_connection_pool()

    @hub.get("/")
    async def html_root():
        return await current_app.send_static_file("index.html")

    @hub.get("/api")
    async def api_root():
        return {"tool": "gator-hub", "version": "1.0"}

    @hub.post("/api/register")
    async def register():
        data = await request.get_json()
        new_reg = tables.Registration(
            id=data["id"],
            layer=data["layer"],
            server_url=data["url"],
            owner=data["owner"],
            timestamp=int(datetime.now().timestamp()),
        )
        data = await tables.Registration.insert(new_reg).returning(
            tables.Registration.uid
        )
        return {"result": "success", "uid": data[0]["uid"]}

    @hub.post("/api/job/<int:job_id>/complete")
    async def complete(job_id: int):
        data = await request.get_json()
        new_cmp = tables.Completion(
            db_file=data["db_file"], timestamp=int(datetime.now().timestamp())
        )
        await tables.Completion.insert(new_cmp)
        await tables.Registration.update(
            {tables.Registration.completion: new_cmp}
        ).where(tables.Registration.uid == job_id)
        return {"result": "success"}

    def lookup_job(func: Callable) -> Callable:
        async def _inner(job_id: int, **kwargs) -> Dict[str, Union[str, int]]:
            reg = (
                await tables.Registration.objects()
                .get(tables.Registration.uid == int(job_id))
                .first()
            )
            return await func(reg, **kwargs)

        _inner.__name__ = func.__name__
        return _inner

    @hub.post("/api/job/<int:job_id>/heartbeat")
    @lookup_job
    async def heartbeat(job: tables.Registration):
        data = await request.get_json()
        for key, value in data.get("metrics", {}).items():
            if await tables.Metric.exists().where(
                (tables.Metric.registration == job) & (tables.Metric.name == key)
            ):
                await tables.Metric.update({tables.Metric.value: value}).where(
                    (tables.Metric.registration == job) & (tables.Metric.name == key)
                )
            else:
                new_mtc = tables.Metric(registration=job, name=key, value=value)
                await tables.Metric.insert(new_mtc)
        return {"result": "success"}

    @hub.get("/api/jobs")
    async def jobs():
        jobs = (
            await tables.Registration.objects(tables.Registration.completion)
            .order_by(tables.Registration.timestamp, ascending=False)
            .output()
            .limit(10)
        )
        data = []
        for job in jobs:
            metrics = await tables.Metric.select(
                tables.Metric.name, tables.Metric.value
            ).where(tables.Metric.registration == job)
            data.append({**job.to_dict(), "metrics": metrics})
        return data

    @hub.get("/api/job/<int:job_id>")
    @hub.get("/api/job/<int:job_id>/")
    @lookup_job
    async def job_info(job):
        # Get all metrics
        metrics = await tables.Metric.select().where(tables.Metric.registration == job)
        # Return data
        return {"result": "success", "job": job.to_dict(), "metrics": metrics}

    @hub.get("/api/job/<int:job_id>/messages")
    @hub.get("/api/job/<int:job_id>/messages/")
    @hub.get("/api/job/<int:job_id>/messages/<path:hierarchy>")
    @lookup_job
    async def job_messages(job, hierarchy: str = ""):
        # Get query parameters
        after_uid = int(request.args.get("after", 0))
        limit_num = int(request.args.get("limit", 10))
        hierarchy = [x for x in hierarchy.split("/") if len(x.strip()) > 0]
        # If necessary, dig down through the hierarchy to find the job
        if hierarchy:
            async with WebsocketClient(job.server_url) as ws:
                data = await ws.resolve(path=hierarchy)
                server_url = data["server_url"]
        # If no hierarchy, we're using the top-level job
        else:
            server_url = job.server_url
        # Query messages via the job's websocket
        async with WebsocketClient(server_url) as ws:
            data = await ws.get_messages(after=after_uid, limit=limit_num)
        # Return data
        return data

    @hub.get("/api/job/<int:job_id>/layer")
    @hub.get("/api/job/<int:job_id>/layer/")
    @hub.get("/api/job/<int:job_id>/layer/<path:hierarchy>")
    @lookup_job
    async def job_layer(job, hierarchy: str = ""):
        # If this is a tier, resolve the hierarchy
        if job.layer == "tier":
            logging.info(f"Resolving tier: {job.id} -> {hierarchy}")
            hierarchy = [x for x in hierarchy.split("/") if len(x.strip()) > 0]
            async with WebsocketClient(job.server_url) as ws:
                return await ws.resolve(path=hierarchy)
        # Otherwise, it's a wrapper so just return the top job
        else:
            logging.info(f"Returning wrapper: {job.id}")
            return {
                "id": job.id,
                "path": [],
                "children": [],
            }

    # Launch
    hub.run(host=host, port=port)
