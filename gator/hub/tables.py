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


from piccolo.columns import ForeignKey, Integer, Serial, Varchar
from piccolo.engine.postgres import PostgresEngine
from piccolo.table import Table


class Completion(Table):
    uid = Serial(primary_key=True, unique=True, index=True)
    db_file = Varchar(5000)
    timestamp = Integer()
    result = Integer()


# Define a registration table format
class Registration(Table):
    uid = Serial(primary_key=True, unique=True, index=True)
    layer = Varchar(16)
    ident = Varchar(250)
    server_url = Varchar(250)
    owner = Varchar(250)
    timestamp = Integer()
    completion = ForeignKey(references=Completion)


# Define a metric table format
class Metric(Table):
    uid = Serial(primary_key=True, unique=True, index=True)
    registration = ForeignKey(references=Registration)
    name = Varchar(250)
    value = Integer()


def setup_db(host: str, port: str, name: str, user: str, password: str):
    # Create a Piccolo Postgres query engine
    db = PostgresEngine(
        config={
            "host": host,
            "port": port,
            "database": name,
            "user": user,
            "password": password,
        }
    )

    for table in (Completion, Registration, Metric):
        table._meta.db = db

    return db
