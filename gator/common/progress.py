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

import math
from functools import lru_cache
from time import monotonic
from typing import Iterable, List, Optional

from rich.color import Color, blend_rgb
from rich.color_triplet import ColorTriplet
from rich.console import Console, ConsoleOptions, RenderResult
from rich.jupyter import JupyterMixin
from rich.measure import Measurement
from rich.segment import Segment
from rich.style import Style, StyleType


class PassFailBar(JupyterMixin):
    """
    Renders a custom progress bar displaying total items to execute, number of
    jobs currently running, number of passes, and the number of failures.

    :param total:   Total number of jobs to run
    :param active:  Number of jobs currently executing
    :param passed:  Number of jobs that passed
    :param failed:  Number of jobs that failed
    :param width:   Width of the bar, or ``None`` for maximum width. Defaults to None.
    :param style:   Style for the bar background. Defaults to "bar.back".
    :param complete_style:  Style for the completed bar. Defaults to "bar.complete".
    :param finished_style:  Style for a finished bar. Defaults to "bar.finished".
    :param animation_time: Time in seconds to use for animation, or None to use system time.
    """

    def __init__(
        self,
        total: int = 100,
        active: int = 0,
        passed: int = 0,
        failed: int = 0,
        width: Optional[int] = None,
        style: StyleType = "bar.back",
        complete_style: StyleType = "bar.complete",
        finished_style: StyleType = "bar.finished",
        animation_time: Optional[float] = None,
    ):
        self.total = total
        self.active = active
        self.passed = passed
        self.failed = failed
        self.width = width
        self.style = style
        self.complete_style = complete_style
        self.finished_style = finished_style
        self.animation_time = animation_time

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

    def update(self, total: int, active: int, passed: int, failed: int) -> None:
        """Update progress with new values.

        Args:
            completed (float): Number of steps completed.
            total (float, optional): Total number of steps, or ``None`` to not change. Defaults to None.
        """
        self.total = total
        self.active = active
        self.passed = passed
        self.failed = failed

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        # Sample the segments

        width = min(self.width or options.max_width, options.max_width)
        ascii = options.legacy_windows or options.ascii_only

        pass_style = console.get_style("green")
        fail_style = console.get_style("red")
        actv_style = console.get_style("default")
        pasv_style = console.get_style("grey23")

        char_full_bar = "-" if ascii else "━"
        char_half_right = " " if ascii else "╸"
        char_half_left = " " if ascii else "╺"

        max_halves = int(width * 2)

        pass_halves = int(max_halves * (self.passed / self.total))
        fail_halves = int(max_halves * (self.failed / self.total))
        actv_halves = int(max_halves * (self.active / self.total))
        pasv_halves = max_halves - sum((pass_halves, fail_halves, actv_halves))

        offset = 0
        for halves, style in ((fail_halves, fail_style),
                              (pass_halves, pass_style),
                              (actv_halves, actv_style),
                              (pasv_halves, pasv_style)):
            halves -= offset
            offset = halves % 2
            yield Segment(((halves + offset) // 2) * char_full_bar, style)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return (
            Measurement(self.width, self.width)
            if self.width is not None
            else Measurement(4, options.max_width)
        )


if __name__ == "__main__":  # pragma: no cover
    console = Console()
    bar = PassFailBar(100, 10, 2, 3)

    import random, time

    console.show_cursor(False)
    total = 100
    max_actv = 3
    last_actv = 0
    passed = 0
    failed = 0
    for _ in range(100):
        max_actv = min(max_actv, total - (passed + failed))
        if max_actv == 0:
            break
        active = random.randint(0, max_actv)
        passed += (num_pass := random.randint(0, last_actv))
        failed += last_actv - num_pass
        last_actv = active
        bar.update(total, active, passed, failed)
        console.print(bar)
        console.file.write("\r")
        time.sleep(0.5)
    console.show_cursor(True)
    console.print()