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
import sys
from pathlib import Path

import click
from rich.console import Console

from . import launch
from . import launch_progress
from .hub.api import HubAPI
from .scheduler import LocalScheduler
from .specs import Spec
from .specs.common import SpecError

@click.command()
@click.option("--id",        default=None,  type=str,          help="Instance identifier")
@click.option("--hub",       default=None,  type=str,          help="URL of a Gator Hub instance")
@click.option("--parent",    default=None,  type=str,          help="Pointer to parent node")
@click.option("--interval",  default=5,     type=int,          help="Polling interval", show_default=True)
@click.option("--tracking",  default=None,  type=click.Path(), help="Tracking directory")
@click.option("--quiet",     default=False, count=True,        help="Silence STDOUT logging")
@click.option("--all-msg",   default=False, count=True,        help="Propagate all messages to the top level")
@click.option("--verbose",   default=False, count=True,        help="Show debug messages")
@click.option("--progress",  default=False, count=True,        help="Show progress bar")
@click.option("--scheduler", default="local",
                             type=click.Choice(("local", ), case_sensitive=False),
                             help="Select the scheduler to use for launching jobs",
                             show_default=True)
@click.argument("spec", type=click.Path(exists=True), required=False)
def main(id        : str,
         hub       : str,
         parent    : str,
         interval  : int,
         tracking  : str,
         quiet     : bool,
         all_msg   : bool,
         verbose   : bool,
         progress  : bool,
         scheduler : str,
         spec      : str) -> None:
    if hub:
        HubAPI.url = hub
    # Determine a tracking directory
    tracking = Path(tracking) if tracking else (Path.cwd() / "tracking")
    # Select the right scheduler
    sched = { "local": LocalScheduler }.get(scheduler.lower())
    # Launch with optional progress tracking
    try:
        asyncio.run((launch_progress if progress else launch).launch(
            id       =id,
            parent   =parent,
            spec     =Path(spec) if spec is not None else None,
            tracking =tracking,
            interval =interval,
            quiet    =quiet,
            all_msg  =all_msg,
            verbose  =verbose,
            scheduler=sched,
        ))
    except SpecError as e:
        con = Console()
        con.log(f"[bold red][ERROR][/bold red] Issue in {type(e.obj).__name__} "
                f"specification field '{e.field}': {str(e)}")
        if hasattr(e.obj, "jobs"):
            e.obj.jobs = ["..."]
        con.log(Spec.dump([e.obj]))
        sys.exit(1)
    except Exception as e:
        con = Console()
        con.log(f"[bold red][ERROR][/bold red] {str(e)}")
        if verbose:
            con.print_exception(show_locals=True)
        sys.exit(1)


if __name__ == "__main__":
    main(prog_name="gator", auto_envvar_prefix="GATOR_")
