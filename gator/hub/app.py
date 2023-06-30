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

import os
from datetime import datetime
from typing import Callable, Dict, Union

from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table
from piccolo.columns import Varchar, Integer, Serial, ForeignKey
from quart import Quart, render_template, request

from ..common.ws_client import WebsocketClient

react_dir = os.environ["GATOR_HUB_ROOT"]

# Create Quart application to host the interface and handle API requests
hub = Quart("gator-hub",
            static_url_path="/assets",
            static_folder=f"{react_dir}/assets",
            template_folder=react_dir)

# Create a Piccolo Postgres query engine
db = PostgresEngine(config={ "host"    : "127.0.0.1",
                             "port"    : 5432,
                             "database": "gator",
                             "user"    : "postgres",
                             "password": "dbpasswd123" })

# Define a completion table format
class Completion(Table, db=db):
    uid       = Serial(primary_key=True, unique=True, index=True)
    db_file   = Varchar(5000)
    timestamp = Integer()

# Define a registration table format
class Registration(Table, db=db):
    uid        = Serial(primary_key=True, unique=True, index=True)
    layer      = Varchar(16)
    id         = Varchar(250)
    server_url = Varchar(250)
    owner      = Varchar(250)
    timestamp  = Integer()
    completion = ForeignKey(references=Completion)

# Define a metric table format
class Metric(Table, db=db):
    uid          = Serial(primary_key=True, unique=True, index=True)
    registration = ForeignKey(references=Registration)
    name         = Varchar(250)
    value        = Integer()


@hub.before_serving
async def start_database():
    global db
    await db.start_connection_pool()
    await Completion.create_table(if_not_exists=True)
    await Registration.create_table(if_not_exists=True)
    await Metric.create_table(if_not_exists=True)

@hub.after_serving
async def stop_database():
    global db
    await db.close_connection_pool()

@hub.get("/")
async def html_root():
    return await render_template("index.html")

@hub.get("/api")
async def api_root():
    return { "tool"   : "gator-hub",
             "version": "1.0" }

@hub.post("/api/register")
async def register():
    data = await request.get_json()
    new_reg = Registration(
        id=data["id"],
        layer=data["layer"],
        server_url=data["url"],
        owner=data["owner"],
        timestamp=int(datetime.now().timestamp())
    )
    data = await Registration.insert(new_reg).returning(Registration.uid)
    return { "result": "success", "uid": data[0]["uid"] }

@hub.post("/api/job/<int:job_id>/complete")
async def complete(job_id : int):
    data = await request.get_json()
    new_cmp = Completion(db_file=data["db_file"],
                         timestamp=int(datetime.now().timestamp()))
    await Completion.insert(new_cmp)
    await Registration.update({ Registration.completion: new_cmp }).where(Registration.uid == job_id)
    return { "result": "success" }

def lookup_job(func : Callable) -> Callable:
    async def _inner(job_id : int, **kwargs) -> Dict[str, Union[str, int]]:
        reg = await Registration.objects().get(Registration.uid == int(job_id)).first()
        return await func(reg, **kwargs)
    setattr(_inner, "__name__", getattr(func, "__name__"))
    return _inner

@hub.post("/api/job/<int:job_id>/heartbeat")
@lookup_job
async def heartbeat(job : Registration):
    data = await request.get_json()
    for key, value in data.get("metrics", {}).items():
        if await Metric.exists().where((Metric.registration == job) &
                                       (Metric.name         == key)):
            await Metric.update({ Metric.value: value }).where((Metric.registration == job) &
                                                               (Metric.name         == key))
        else:
            new_mtc = Metric(registration=job, name=key, value=value)
            await Metric.insert(new_mtc)
    return { "result": "success" }

@hub.get("/api/jobs")
async def jobs():
    jobs = await Registration.objects(Registration.completion).order_by(
        Registration.timestamp, ascending=False
    ).output().limit(10)
    data = []
    for job in jobs:
        metrics = await Metric.select(Metric.name, Metric.value).where(Metric.registration == job)
        data.append({ **job.to_dict(), "metrics": metrics })
    return data

@hub.get("/api/job/<int:job_id>")
@hub.get("/api/job/<int:job_id>/")
@lookup_job
async def job_info(job : Registration):
    # Get all metrics
    metrics = await Metric.select().where(Metric.registration == job)
    # Return data
    return {
        "result" : "success",
        "job"    : job.to_dict(),
        "metrics": metrics
    }

@hub.get("/api/job/<int:job_id>/messages")
@hub.get("/api/job/<int:job_id>/messages/")
@hub.get("/api/job/<int:job_id>/messages/<path:hierarchy>")
@lookup_job
async def job_messages(job : Registration, hierarchy : str=""):
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
async def job_layer(job : Registration, hierarchy : str=""):
    # If this is a tier, resolve the hierarchy
    if job.layer == "tier":
        print(f"Resolving tier: {job.id} -> {hierarchy}")
        hierarchy = [x for x in hierarchy.split("/") if len(x.strip()) > 0]
        async with WebsocketClient(job.server_url) as ws:
            return await ws.resolve(path=hierarchy)
    # Otherwise, it's a wrapper so just return the top job
    else:
        print(f"Returning wrapper: {job.id}")
        return { "id"      : job.id,
                 "path"    : [],
                 "children": [], }

if __name__ == "__main__":
    hub.run(port=8080)
