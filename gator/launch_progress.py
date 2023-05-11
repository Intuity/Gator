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
from rich.tree import Tree

from .launch import launch as launch_base


async def launch(**kwargs) -> None:
    # Create console
    console = Console(log_path=False)
    # Create table
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
    def _update(_, sub_total, sub_active, sub_passed, sub_failed, tree=None, **__):
        # Update the progress bars
        progbar.update(bar_total,  total=sub_total, completed=(sub_passed + sub_failed))
        progbar.update(bar_active, total=sub_total, completed=sub_active)
        progbar.update(bar_passed, total=sub_total, completed=sub_passed)
        progbar.update(bar_failed, total=sub_total, completed=sub_failed)
        # Display the tree
        if tree:
            def _chase(parent, segment):
                for key, value in segment.items():
                    branch = parent.add(key)
                    if isinstance(value, dict):
                        _chase(branch, value)
            r_tree = Tree("Root")
            _chase(r_tree, tree)
            console.log(r_tree)
    prog_cb = _update
    # Start console
    live = Live(table, refresh_per_second=4, console=console)
    live.start(refresh=True)
    # Launch
    await launch_base(**kwargs, heartbeat_cb=prog_cb, console=live.console)
    # Wait a little so the final progress update happens
    await asyncio.sleep(1)
    # Stop the console
    live.stop()
