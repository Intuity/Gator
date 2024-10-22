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

from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.jupyter import JupyterMixin
from rich.live import Live
from rich.measure import Measurement
from rich.table import Table

from .summary import Summary


class PassFailBar(JupyterMixin):
    """
    Renders a custom progress bar displaying total items to execute, number of
    jobs currently running, number of passes, and the number of failures.

    :param title:         Title to display
    :param total:         Total number of jobs to run
    :param active:        Number of jobs currently executing
    :param passed:        Number of jobs that passed
    :param failed:        Number of jobs that failed
    :param width:         Fix the width of the bar
    :param fail_style:    Style used to indicate failures
    :param pass_style:    Style used to indicate passes
    :param active_style:  Style used for active jobs
    :param passive_style: Style used for not yet started jobs
    """

    def __init__(
        self,
        title: str,
        total: int = 100,
        active: int = 0,
        passed: int = 0,
        failed: int = 0,
        width: Optional[int] = None,
        fail_style: str = "red",
        pass_style: str = "green",
        active_style: str = "white",
        passive_style: str = "grey23",
    ):
        self.title = title
        self.total = total
        self.active = active
        self.passed = passed
        self.failed = failed
        self.width = width
        self.fail_style = fail_style
        self.pass_style = pass_style
        self.active_style = active_style
        self.passive_style = passive_style

    def __repr__(self) -> str:
        return f"<Bar {self.completed!r} of {self.total!r}>"

    @property
    def percentage_completed(self) -> Optional[float]:
        """Calculate percentage complete."""
        if self.total is None:
            return None
        completed = (self.completed / self.total) * 100.0
        completed = min(100, max(0.0, completed))
        return completed

    def update(self, summary: Summary) -> None:
        """Update progress with new values.

        Args:
            completed (float): Number of steps completed.
            total (float, optional): Total number of steps, or ``None`` to not change.
            Defaults to None.
        """
        self.total = summary["metrics"].get("sub_total", 1)
        self.active = summary["metrics"].get("sub_active", 0)
        self.passed = summary["metrics"].get("sub_passed", 0)
        self.failed = summary["metrics"].get("sub_failed", 0)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        # Ensure space for the title text
        title_width = len(self.title) + 1
        # Ensure space for the progress detail i.e. '1/2/3/4'
        detail_width = (len(str(self.total)) + 2) * 4

        # Determine the width available for the progress bar
        width = min(self.width or options.max_width, options.max_width)
        width -= title_width + detail_width + 1

        # Determine if unicode fully supported
        using_ascii = options.legacy_windows or options.ascii_only
        char_full_bar = "-" if using_ascii else "━"

        # Work out the sizes of each part of the progress bar
        max_halves = int(width * 2)
        pass_halves = int(max_halves * (self.passed / self.total))
        fail_halves = int(max_halves * (self.failed / self.total))
        actv_halves = int(max_halves * (self.active / self.total))
        pasv_halves = max_halves - sum((pass_halves, fail_halves, actv_halves))

        # Draw each bar segment
        offset = 0
        segments = ""
        for halves, style in (
            (fail_halves, self.fail_style),
            (pass_halves, self.pass_style),
            (actv_halves, self.active_style),
            (pasv_halves, self.passive_style),
        ):
            # Round-up/down to compensate for partial bars
            halves -= offset
            offset = halves % 2
            num_chars = min(((halves + offset) // 2), width - offset)
            segments += f"[{style}]"
            segments += num_chars * char_full_bar
            segments += f"[/{style}]"

        # Draw the progress bar
        table = Table(
            expand=True,
            collapse_padding=True,
            show_header=False,
            show_footer=False,
            box=None,
            padding=0,
        )
        table.add_column(width=title_width)
        table.add_column()
        table.add_column(width=detail_width, justify="right")
        max_chars = len(str(self.total))
        table.add_row(
            f"[default]{self.title}[/default]",
            segments,
            f"[on green] {self.passed:{max_chars}d} [/on green]"
            f"[on red] {self.failed:{max_chars}d} [/on red]"
            f"[on default] {self.active:{max_chars}d} [/on default]"
            f"[on grey23] {self.total:{max_chars}d} [/on grey23]",
        )
        yield table

    def __rich_measure__(self, console: Console, options: ConsoleOptions) -> Measurement:
        return (
            Measurement(self.width, self.width)
            if self.width is not None
            else Measurement(4, options.max_width)
        )


if __name__ == "__main__":  # pragma: no cover
    console = Console()
    bar = PassFailBar("Regression", 100, 0, 0, 0)

    import random
    import time

    console.show_cursor(False)
    total = 100
    max_actv = 3
    last_actv = 0
    passed = 0
    failed = 0
    with Live(bar, refresh_per_second=4) as live:
        for _ in range(100):
            max_actv = min(max_actv, total - (passed + failed))
            if max_actv <= 0:
                break
            active = random.randint(0, max_actv)
            passed += (num_pass := random.randint(0, last_actv))
            failed += last_actv - num_pass
            last_actv = active
            bar.update(total, active, passed, failed)
            live.update(bar)
            time.sleep(0.25)
    console.show_cursor(True)
    console.print()
