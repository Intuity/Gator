# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
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
import os
from pathlib import Path
from typing import Union

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.rule import Rule
from rich.table import Table
from rich.tree import Tree

from .common.layer import BaseLayer
from .common.progress import PassFailBar
from .common.summary import Summary
from .common.types import ApiJob
from .launch import launch as launch_base


class ProgressDisplay:
    """
    Display element for task progress including failed tasks, running tasks
    and a progress bar.
    """

    def __init__(self, glyph: str, max_fails: int = 10, max_running: int = 10):
        self.max_rows = 10
        self.bar = PassFailBar(glyph, 1, 0, 0, 0)
        self.failures: dict[str, ApiJob] = {}
        self.running: dict[str, ApiJob] = {}
        self.max_fails = max_fails
        self.max_running = max_running

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        if self.failures:
            yield Rule("▼ Failed Jobs ▼")

            fail_table = Table(
                expand=True,
                show_header=False,
                show_footer=False,
                collapse_padding=True,
                show_lines=False,
                show_edge=False,
                border_style="none",
                box=None,
                padding=0,
            )

            for i, (ident, job) in enumerate(self.failures.items()):
                if i > self.max_fails:
                    fail_table.add_row("", f"and {i - self.max_fails} more...")
                    break
                messages = (Path(job["db_file"]).parent / "messages.log").as_posix()
                fail_table.add_row(ident, messages)

            yield fail_table

        yield self.bar

        if self.running:
            run_table = Table(
                expand=True,
                show_header=False,
                show_footer=False,
                collapse_padding=True,
                show_lines=False,
                show_edge=False,
                border_style="none",
                box=None,
                padding=0,
            )

            for i, (ident, job) in enumerate(self.running.items()):
                if i > self.max_running:
                    run_table.add_row("", f"and {i - self.max_running} more...")
                    break
                messages = (Path(job["db_file"]).parent / "messages.log").as_posix()
                run_table.add_row(ident, messages)

            yield run_table

            yield Rule("▲ Running Jobs ▲")

    async def update(self, layer: BaseLayer, summary: Summary):
        self.bar.update(summary)

        for job_id in summary.failed_ids:
            display_id = ".".join(job_id)
            if display_id in self.failures:
                continue
            job = await layer.resolve(job_id[1:])
            self.failures[display_id] = job

        running = {}
        for job_id in summary.running_ids:
            display_id = ".".join(job_id)
            job = await layer.resolve(job_id[1:])
            running[display_id] = job
        self.running = running


async def launch(glyph: str = "🐊 Gator", **kwargs) -> Summary:
    # Create console
    # Unset COLUMNS and LINES as they prevent automatic resizing
    console = Console(log_path=False, _environ={**os.environ, "COLUMNS": "", "LINES": ""})
    # Create progress display
    progress = ProgressDisplay(glyph, 5)

    # Start console
    live = Live(progress, refresh_per_second=4, console=console)
    live.start(refresh=True)

    # Create an update function
    async def _update(layer: BaseLayer, summary: Summary, /, tree: Union[Tree, None] = None):
        # Update the progress display
        await progress.update(layer, summary)

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

    # Launch
    summary = await launch_base(**kwargs, heartbeat_cb=_update, console=live.console)
    # Wait a little so the final progress update happens
    await asyncio.sleep(1)
    # Stop the console
    live.stop()
    # Return the summary
    return summary
