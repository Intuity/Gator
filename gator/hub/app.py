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

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Union, cast

from quart import (
    Quart,
    current_app,
    request,
)

from ..common.db_client import resolve_client
from ..common.types import (
    ApiChildren,
    ApiJob,
    ApiMessagesResponse,
    ApiResolvable,
    JobResult,
    JobState,
)
from .tables import Completion, Metric, Registration, setup_db


@asynccontextmanager
async def registration_client(registration: Registration):
    completion = cast(Optional[Completion], await registration.get_related(Registration.completion))
    db_file = completion.db_file if completion else ""
    try:
        async with resolve_client(
            ApiResolvable(
                server_url=registration.server_url,
                db_file=db_file,
                status=JobState.COMPLETE if completion else JobState.STARTED,
            )
        ) as cli:
            yield cli
    finally:
        pass


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
    db = setup_db(db_host, db_port, db_name, db_user, db_pwd)

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
        await Completion.create_table(if_not_exists=True)
        await Registration.create_table(if_not_exists=True)
        await Metric.create_table(if_not_exists=True)

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
        new_reg = Registration(
            {
                Registration.ident: data["ident"],
                Registration.layer: data["layer"],
                Registration.server_url: data["url"],
                Registration.owner: data["owner"],
                Registration.timestamp: int(datetime.now().timestamp()),
            }
        )
        data = await Registration.insert(new_reg).returning(Registration.uid)
        return {"result": "success", "uid": data[0]["uid"]}

    @hub.post("/api/job/<int:job_id>/complete")
    async def complete(job_id: int):
        data = await request.get_json()
        new_cmp = Completion(
            {
                Completion.db_file: data["db_file"],
                Completion.result: data["result"],
                Completion.timestamp: int(datetime.now().timestamp()),
            }
        )
        await Completion.insert(new_cmp)
        await Registration.update({Registration.completion: new_cmp}).where(
            Registration.uid == job_id
        )
        return {"result": "success"}

    def lookup_job(func: Callable) -> Callable:
        async def _inner(job_id: int, **kwargs) -> Dict[str, Union[str, int]]:
            reg = await Registration.objects().get(Registration.uid == int(job_id)).first()
            return await func(reg, **kwargs)

        _inner.__name__ = func.__name__
        return _inner

    @hub.post("/api/job/<int:job_id>/heartbeat")
    @lookup_job
    async def heartbeat(job: Registration):
        data = await request.get_json()
        for key, value in data.get("metrics", {}).items():
            if await Metric.exists().where((Metric.registration == job) & (Metric.name == key)):
                await Metric.update({Metric.value: value}).where(
                    (Metric.registration == job) & (Metric.name == key)
                )
            else:
                new_mtc = Metric({Metric.registration: job, Metric.name: key, Metric.value: value})
                await Metric.insert(new_mtc)
        return {"result": "success"}

    @hub.get("/api/jobs")
    async def jobs() -> ApiChildren:
        before = int(request.args.get("before", 0))
        after = int(request.args.get("after", 0))
        limit = int(request.args.get("limit", 10))
        window_condition = (
            ((Registration.uid > after) & (Registration.uid < before))
            if after < before
            else ((Registration.uid > after) | (Registration.uid < before))
        )
        registrations = (
            await Registration.objects(Registration.completion)
            .where(window_condition)
            .order_by(Registration.uid, ascending=False)
            .output()
            .limit(limit)
        )
        children: list[ApiJob] = []
        for registration in registrations:
            list_metrics = await Metric.select(Metric.name, Metric.value).where(
                Metric.registration == registration
            )
            metrics = {m["name"]: m["value"] for m in list_metrics}
            start = registration.timestamp

            completion = registration.completion
            if completion.uid is not None:
                db_file = completion.db_file
                status = JobState.COMPLETE
                stop = completion.timestamp
                result = cast(JobResult, completion.result)
            else:
                db_file = ""
                status = JobState.STARTED
                stop = None
                result = JobResult.UNKNOWN
            children.append(
                ApiJob(
                    uidx=registration.uid,
                    root=registration.uid,
                    path=[],
                    ident=registration.ident,
                    owner=registration.owner,
                    status=status,
                    metrics=metrics,
                    server_url=registration.server_url,
                    db_file=db_file,
                    started=start,
                    updated=stop or start,
                    stopped=stop,
                    result=result,
                    children=[],
                    expected_children=registration.layer == "tier",
                )
            )

        return {"children": children, "status": JobState.STARTED}

    @hub.get("/api/job/<int:job_id>")
    @hub.get("/api/job/<int:job_id>/")
    @lookup_job
    async def job_info(job: Registration):
        # Get all metrics
        metrics = await Metric.select().where(Metric.registration == job)
        # Return data
        return {"result": "success", "job": job.to_dict(), "metrics": metrics}

    @hub.get("/api/job/<int:job_id>/messages")
    @hub.get("/api/job/<int:job_id>/messages/")
    @hub.get("/api/job/<int:job_id>/messages/<path:hierarchy>")
    @lookup_job
    async def job_messages(registration: Registration, hierarchy: str = "") -> ApiMessagesResponse:
        # Get query parameters
        after_uid = int(request.args.get("after", 0))
        limit_num = int(request.args.get("limit", 10))
        path = [stripped for el in hierarchy.split("/") if (stripped := el.strip())][1:]
        # If necessary, dig down through the hierarchy to find the job
        async with registration_client(registration) as cli:
            job = await cli.resolve(path)
        # Query messages via the job's websocket
        async with resolve_client(job) as cli:
            data = await cli.get_messages(after=after_uid, limit=limit_num)

        # Return data
        return data

    @hub.get("/api/job/<int:job_id>/resolve")
    @hub.get("/api/job/<int:job_id>/resolve/")
    @hub.get("/api/job/<int:job_id>/resolve/<path:hierarchy>")
    @lookup_job
    async def job_resolve(job: Registration, hierarchy: str = "") -> ApiJob:
        path = [stripped for el in hierarchy.split("/") if (stripped := el.strip())][1:]
        nest_path = [
            stripped
            for el in request.args.get("nest_path", "root").split("/")
            if (stripped := el.strip())
        ][1:]
        depth = int(request.args.get("depth", 1))

        async with registration_client(job) as cli:
            return await cli.resolve(path, nest_path=nest_path, depth=depth)

    # Launch
    hub.run(host=host, port=port)
