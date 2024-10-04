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
from pathlib import Path
import os

import click

from .app import setup_hub


@click.command()
# HTTP
@click.option("--host", "-H", default="0.0.0.0", type=str)
@click.option("--port", "-P", default=8080, type=int)
@click.option(
    "--static",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path(
        os.environ.get("GATOR_HUB_ROOT", Path(__file__).parent.parent.parent / "gator-hub")
    ),
)
# Postgres DB
@click.option("--db-host", default="127.0.0.1", type=str)
@click.option("--db-port", default=5432, type=int)
@click.option("--db-name", default="postgres", type=str)
@click.option("--db-user", default="postgres", type=str)
@click.option("--db-pwd", default="dbpasswd123", type=str)
def hub(
    host: str,
    port: int,
    static: Path,
    db_host: str,
    db_port: str,
    db_name: str,
    db_user: str,
    db_pwd: str,
):
    setup_hub(host, port, static, db_host, db_port, db_name, db_user, db_pwd)


if __name__ == "__main__":
    hub()
