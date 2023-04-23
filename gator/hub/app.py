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

from flask import Flask, request

from ..common.db import Database
from ..types import Attribute

hub = Flask("gator-hub")

# Local SQLite database
@dataclasses.dataclass
class Registration:
    id         : str
    server_url : str
    timestamp  : datetime = dataclasses.field(default_factory=datetime.now)

db = Database(path=Path.cwd() / "hub.sqlite", uwsgi=True)
db.register(Attribute)
db.register(Registration)

db.push_attribute(Attribute("last_start", datetime.now().isoformat()))
db.push_attribute(Attribute("running_on", socket.gethostname()))

@hub.get("/")
def root():
    return { "tool"   : "gator-hub",
             "version": "1.0" }

@hub.post("/register")
def register():
    data = request.json
    db.push(reg := Registration(id=data["id"], server_url=data["url"]))
    print(f"Process registered {reg.id}, {reg.server_url}")
    return { "result": "success" }

@hub.get("/jobs")
def jobs():
    return [vars(x) for x in db.get(Registration)]