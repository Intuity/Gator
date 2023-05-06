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

import asyncio
from pathlib import Path

import click

from . import launch
from . import launch_progress
from .common.ws_client import WebsocketClient
from .hub.api import HubAPI


@click.command()
@click.option("--id",       default=None,  type=str,          help="Instance identifier")
@click.option("--hub",      default=None,  type=str,          help="URL of a Gator Hub instance")
@click.option("--parent",   default=None,  type=str,          help="Pointer to parent node")
@click.option("--interval", default=5,     type=int,          help="Polling interval", show_default=True)
@click.option("--tracking", default=None,  type=click.Path(), help="Tracking directory")
@click.option("--quiet",    default=False, count=True,        help="Silence STDOUT logging")
@click.option("--all-msg",  default=False, count=True,        help="Propagate all messages to the top level")
@click.option("--progress", default=False, count=True,        help="Show progress bar")
@click.argument("spec", type=click.Path(exists=True), required=False)
def main(id       : str,
         hub      : str,
         parent   : str,
         interval : int,
         tracking : str,
         quiet    : bool,
         all_msg  : bool,
         progress : bool,
         spec     : str) -> None:
    if hub:
        HubAPI.url = hub
    if parent:
        WebsocketClient.address = parent
    # Determine a tracking directory
    tracking = Path(tracking) if tracking else (Path.cwd() / "tracking")
    # Launch with optional progress tracking
    asyncio.run((launch_progress if progress else launch).launch(
        id      =id,
        spec    =Path(spec) if spec is not None else None,
        tracking=tracking,
        interval=interval,
        quiet   =quiet,
        all_msg =all_msg
    ))


if __name__ == "__main__":
    main(prog_name="gator", auto_envvar_prefix="GATOR_")
