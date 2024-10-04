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
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.markup import escape

from . import launch, launch_progress
from .common.logger import MessageLimits
from .scheduler import LocalScheduler
from .specs import Spec
from .specs.common import SpecError


@click.command()
@click.option("--id", "ident", default=None, type=str, help="Instance identifier")
@click.option("--hub", default=None, type=str, help="URL of a Gator Hub instance")
@click.option("--parent", default=None, type=str, help="Pointer to parent node")
@click.option(
    "--interval",
    default=5,
    type=int,
    help="Polling interval",
    show_default=True,
)
@click.option("--tracking", default=None, type=click.Path(), help="Tracking directory")
@click.option("--quiet", default=False, count=True, help="Silence STDOUT logging")
@click.option(
    "--all-msg",
    default=False,
    count=True,
    help="Propagate all messages to the top level",
)
@click.option("--verbose", default=False, count=True, help="Show debug messages")
@click.option("--progress", default=False, count=True, help="Show progress bar")
@click.option(
    "--scheduler",
    default="local",
    type=click.Choice(("local",), case_sensitive=False),
    help="Select the scheduler to use for launching jobs",
    show_default=True,
)
@click.option("--sched-arg", multiple=True, type=str, help="Arguments to the scheduler")
@click.option(
    "--limit-warning",
    type=int,
    default=None,
    help="Maximum number of warning messages before failure",
)
@click.option(
    "--limit-error",
    type=int,
    default=0,
    help="Maximum number of error messages before failure",
)
@click.option(
    "--limit-critical",
    type=int,
    default=0,
    help="Maximum number of critical messages before failure",
)
@click.argument("spec", type=click.Path(exists=True), required=False)
def main(
    ident: str,
    hub: str,
    parent: str,
    interval: int,
    tracking: str,
    quiet: bool,
    all_msg: bool,
    verbose: bool,
    progress: bool,
    scheduler: str,
    sched_arg: List[str],
    limit_warning: Optional[int],
    limit_error: int,
    limit_critical: int,
    spec: str,
) -> None:
    # Determine a tracking directory
    tracking = (
        Path(tracking)
        if tracking
        else (Path.cwd() / "tracking" / datetime.now().isoformat())
    )
    tracking.mkdir(parents=True, exist_ok=True)
    # Select the right scheduler
    sched = {"local": LocalScheduler}.get(scheduler.lower())
    # Break apart scheduler options as '<KEY>=<VALUE>'
    sched_opts = {}
    for arg in sched_arg:
        if arg.count("=") != 1:
            con = Console()
            con.log(
                f"[bold red][ERROR][/bold red] Malformed scheduler argument "
                f"cannot be parsed as <KEY>=<VALUE>: {escape(arg)}"
            )
            sys.exit(1)
        key, val = arg.split("=")
        sched_opts[key.strip()] = val.strip()
    # Launch with optional progress tracking
    try:
        asyncio.run(
            (launch_progress if progress else launch).launch(
                ident=ident,
                hub=hub,
                parent=parent,
                spec=Path(spec) if spec is not None else None,
                tracking=tracking,
                interval=interval,
                quiet=quiet,
                all_msg=all_msg,
                verbose=verbose,
                scheduler=sched,
                sched_opts=sched_opts,
                limits=MessageLimits(
                    warning=limit_warning,
                    error=limit_error,
                    critical=limit_critical,
                ),
            )
        )
    except SpecError as e:
        console_file = (Path(tracking) / "error.log").open("a") if parent else None
        con = Console(file=console_file)
        con.log(
            f"[bold red][ERROR][/bold red] Issue in {type(e.obj).__name__} "
            f"specification field '{e.field}': {escape(str(e))}"
        )
        if hasattr(e.obj, "jobs"):
            e.obj.jobs = ["..."]
        con.log(Spec.dump([e.obj]))
        sys.exit(1)
    except Exception:
        console_file = (Path(tracking) / "error.log").open("a") if parent else None
        con = Console(file=console_file)
        con.log(traceback.format_exc())
        if verbose:
            con.print_exception(show_locals=True)
        sys.exit(1)


if __name__ == "__main__":
    main(prog_name="gator", auto_envvar_prefix="GATOR_")
