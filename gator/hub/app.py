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

import dataclasses
import os
import socket
from datetime import datetime
from pathlib import Path

from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table
from piccolo.columns import Varchar, Integer, UUID
from quart import Quart, render_template, request

from ..common.db import Base, Database
from ..common.types import Attribute

react_dir = os.environ["GATOR_HUB_ROOT"]
print(f"Static content: {react_dir}")

hub = Quart("gator-hub",
            static_url_path="/assets",
            static_folder=f"{react_dir}/assets",
            template_folder=react_dir)

db = PostgresEngine(config={ "host"    : "127.0.0.1",
                             "port"    : 5432,
                             "database": "gator",
                             "user"    : "postgres",
                             "password": "dbpasswd123" })

class Registration(Table, db=db):
    uuid       = UUID(primary_key=True)
    id         = Varchar(250)
    server_url = Varchar(250)
    timestamp  = Integer()

@hub.before_serving
async def start_database():
    global db
    await db.start_connection_pool()
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
    await Registration.insert(Registration(id=data["id"],
                                           server_url=data["url"],
                                           timestamp=int(datetime.now().timestamp())))
    return { "result": "success" }

@hub.get("/api/jobs")
async def jobs():
    regs = await Registration.select().order_by(Registration.timestamp, ascending=False).limit(10)
    return regs

if __name__ == "__main__":
    hub.run(port=8080)
