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
import socket
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request
import uwsgi

from ..common.db import Base, Database
from ..common.types import Attribute

react_dir = uwsgi.opt["react_root"].decode("utf-8")
print(f"Static content: {react_dir}")

hub = Flask("gator-hub",
            static_url_path="/assets",
            static_folder=f"{react_dir}/assets",
            template_folder=react_dir)

# Local SQLite database
@dataclasses.dataclass
class Registration(Base):
    id         : str      = ""
    server_url : str      = ""
    timestamp  : datetime = dataclasses.field(default_factory=datetime.now)

db = Database(path=Path.cwd() / "hub.sqlite", uwsgi=True)
db.register(Attribute)
db.register(Registration)

db.push_attribute(Attribute(name="last_start", value=datetime.now().isoformat()))
db.push_attribute(Attribute(name="running_on", value=socket.gethostname()))

@hub.get("/")
def html_root():
    return render_template("index.html")

@hub.get("/api")
def api_root():
    return { "tool"   : "gator-hub",
             "version": "1.0" }

@hub.post("/api/register")
def register():
    data = request.json
    uid = db.push(reg := Registration(id=data["id"], server_url=data["url"]))
    print(f"Process registered {reg.id}, {reg.server_url}")
    return { "result": "success", "uid": uid }

@hub.get("/api/jobs")
def jobs():
    return [vars(x) for x in db.get(Registration,
                                    sql_order_by=("timestamp", False),
                                    sql_limit   =10)]
