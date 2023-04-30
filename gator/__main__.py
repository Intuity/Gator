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
from typing import Callable, Optional, Union

import click
from rich.progress import (BarColumn,
                           MofNCompleteColumn,
                           Progress,
                           SpinnerColumn,
                           TaskProgressColumn,
                           TextColumn)

from .common.client import Client
from .common.logger import local_console
from .hub.api import HubAPI
from .layer import Layer
from .specs import Job, JobArray, JobGroup, Spec
from .wrapper import Wrapper



async def launch(id           : Optional[str]               = None,
                 spec         : Optional[Union[Spec, Path]] = None,
                 tracking     : Path                        = Path.cwd(),
                 interval     : int                         = 5,
                 quiet        : bool                        = False,
                 all_msg      : bool                        = False,
                 heartbeat_cb : Optional[Callable]          = None) -> None:
    # Start client
    await Client.instance().start()
    # Work out where the spec is coming from
    if spec is None and Client.instance().linked and id:
        raw_spec = await Client.instance().spec(id=id)
        spec     = Spec.parse_str(raw_spec.get("spec", ""))
    elif spec is not None and not isinstance(spec, Spec):
        spec = Spec.parse(Path(spec))
    else:
        raise Exception("No specification file provided and no parent server to query")
    # If an ID has been provided, override whatever the spec gives
    if id is not None:
        spec.id = id
    # If a JobGroup is provided, launch a layer
    if isinstance(spec, (JobArray, JobGroup)):
        await Layer.create(spec         =spec,
                            tracking    =tracking,
                            quiet       =quiet and not all_msg,
                            all_msg     =all_msg,
                            heartbeat_cb=heartbeat_cb)
    # If a Job is provided, launch a wrapper
    elif isinstance(spec, Job):
        await Wrapper.create(spec    =spec,
                             tracking=tracking,
                             interval=interval,
                             quiet   =quiet and not all_msg)
    # Unsupported forms
    else:
        raise Exception(f"Unsupported specification object of type {type(spec).__name__}")


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
        Client(address=parent)
    # Determine a tracking directory
    tracking = Path(tracking) if tracking else (Path.cwd() / "tracking")
    # Create a progress bar
    progbar = None
    prog_cb = None
    if progress:
        progbar = Progress(TextColumn("Gator 🐊"),
                           SpinnerColumn(),
                           BarColumn(bar_width=None),
                           MofNCompleteColumn(),
                           TaskProgressColumn(),
                           console=local_console,
                           expand=True,
                           refresh_per_second=5)
        progbar.start()
        tracker = progbar.add_task("Running", total=1)
        def _update(sub_total, sub_active, sub_passed, sub_failed, **_):
            progbar.update(tracker, total=sub_total, completed=(sub_passed + sub_failed))
        prog_cb = _update
    # Launch
    asyncio.run(launch(id          =id,
                       spec        =Path(spec) if spec is not None else None,
                       tracking    =tracking,
                       interval    =interval,
                       quiet       =quiet,
                       all_msg     =all_msg,
                       heartbeat_cb=prog_cb))
    # Stop the progress bar
    if progbar:
        progbar.stop()


if __name__ == "__main__":
    main(prog_name="gator", auto_envvar_prefix="GATOR_")
