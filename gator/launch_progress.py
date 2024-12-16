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

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.tree import Tree

from .common.layer import BaseLayer
from .common.progress import PassFailBar
from .common.summary import Summary
from .launch import launch as launch_base


async def launch(glyph: str = "🐊 Gator", **kwargs) -> Summary:
    # Create console
    console = Console(log_path=False)
    # Create table
    table = Table(expand=True, show_edge=False, show_header=False)
    # Create a progress bar
    bar = PassFailBar(glyph, 1, 0, 0, 0)
    table.add_row(bar)
    # Start console
    live = Live(table, refresh_per_second=4, console=console)
    live.start(refresh=True)

    # Create an update function
    def _update(_layer: BaseLayer, summary: Summary, /, tree: Tree | None = None):
        # Update the progress bars
        bar.update(summary)
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
