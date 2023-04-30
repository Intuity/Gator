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
from time import sleep
from typing import Callable, Optional, Union

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn,
                           MofNCompleteColumn,
                           Progress,
                           SpinnerColumn,
                           TaskProgressColumn,
                           TextColumn)
from rich.table import Table
from rich.text import Text

from .common.client import Client
from .common.logger import Logger
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
    # If a JobArray or JobGroup is provided, launch a layer
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
    # Create a console
    prog_cb = None
    if progress:
        table = Table(expand=True, show_edge=False, show_header=False)
        # Create a progress bar
        progbar = Progress(TextColumn("{task.description}"),
                           SpinnerColumn(),
                           BarColumn(bar_width=None),
                           MofNCompleteColumn(),
                           TaskProgressColumn(),
                           expand=True)
        table.add_row(Panel(progbar, title="Gator :crocodile:"))
        # Create a progress bar
        bar_total  = progbar.add_task("Completed",     total=1)
        bar_active = progbar.add_task("[cyan]Running", total=1)
        bar_passed = progbar.add_task("[green]Passed", total=1)
        bar_failed = progbar.add_task("[red]Failed",   total=1)
        def _update(sub_total, sub_active, sub_passed, sub_failed, **_):
            progbar.update(bar_total,  total=sub_total, completed=(sub_passed + sub_failed))
            progbar.update(bar_active, total=sub_total, completed=sub_active)
            progbar.update(bar_passed, total=sub_total, completed=sub_passed)
            progbar.update(bar_failed, total=sub_total, completed=sub_failed)
        prog_cb = _update
        # Start console
        console = Console(log_path=False)
        live = Live(table, refresh_per_second=4, console=console)
        Logger.CONSOLE = live.console
        live.start(refresh=True)
    # Launch
    asyncio.run(launch(id          =id,
                       spec        =Path(spec) if spec is not None else None,
                       tracking    =tracking,
                       interval    =interval,
                       quiet       =quiet,
                       all_msg     =all_msg,
                       heartbeat_cb=prog_cb))
    # Wait a little so the final progress update happens
    sleep(1)
    # Stop the console
    if progress:
        live.stop()


if __name__ == "__main__":
    main(prog_name="gator", auto_envvar_prefix="GATOR_")
