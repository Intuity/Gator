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
    timestamp  = Integer()
    completion = ForeignKey(references=Completion)


@hub.before_serving
async def start_database():
    global db
    await db.start_connection_pool()
    await Completion.create_table(if_not_exists=True)
    await Registration.create_table(if_not_exists=True)

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
        timestamp=int(datetime.now().timestamp())
    )
    data = await Registration.insert(new_reg).returning(Registration.uid)
    return { "result": "success", "uid": data[0]["uid"] }

@hub.post("/api/complete")
async def complete():
    data = await request.get_json()
    new_cmp = Completion(db_file=data["db_file"],
                         timestamp=int(datetime.now().timestamp()))
    await Completion.insert(new_cmp)
    await Registration.update({ Registration.completion: new_cmp }).where(Registration.uid == data["uid"])
    return { "result": "success" }

@hub.get("/api/jobs")
async def jobs():
    regs = await Registration.select(
        *Registration.all_columns(),
        *Registration.completion.all_columns()
    ).order_by(
        Registration.timestamp,
        ascending=False
    ).output(nested=True).limit(10)
    return regs

@hub.get("/api/job/<int:job_id>/messages")
async def job_messages(job_id : int):
    # Get query parameters
    after_uid = int(request.args.get("after", 0))
    limit_num = int(request.args.get("limit", 10))
    # Locate the matching job
    reg = await Registration.objects().get(Registration.uid == int(job_id)).first()
    async with WebsocketClient(reg.server_url) as ws:
        data = await ws.get_messages(after=after_uid, limit=limit_num)
    return data

@hub.get("/api/job/<int:job_id>/layer")
@hub.get("/api/job/<int:job_id>/layer/")
@hub.get("/api/job/<int:job_id>/layer/<path:hierarchy>")
async def job_layer(job_id : int, hierarchy : str=""):
    # Get the registered object
    reg = await Registration.objects().get(Registration.uid == int(job_id)).first()
    # If this is a tier, resolve the hierarchy
    if reg.layer == "tier":
        print(f"Resolving tier: {reg.id} -> {hierarchy}")
        hierarchy = [x for x in hierarchy.split("/") if len(x.strip()) > 0]
        async with WebsocketClient(reg.server_url) as ws:
            return await ws.resolve(path=hierarchy)
    # Otherwise, it's a wrapper so just return the top job
    else:
        print(f"Returning wrapper: {reg.id}")
        return { "id"      : reg.id,
                 "path"    : [],
                 "children": [], }

if __name__ == "__main__":
    hub.run(port=8080)
