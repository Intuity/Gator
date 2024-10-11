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

import abc
import functools
import itertools
from typing import Any, Dict, List, Optional, Type

from ..common.child import Child
from ..common.logger import Logger, MessageLimits


class SchedulerError(Exception):
    pass


class BaseScheduler:
    """Launches a set of tasks on a particular infrastructure"""

    def __init__(
        self,
        parent: str,
        interval: int = 5,
        quiet: bool = True,
        logger: Optional[Logger] = None,
        options: Optional[Dict[str, str]] = None,
        limits: Optional[MessageLimits] = None,
    ) -> None:
        self.parent = parent
        self.interval = interval
        self.quiet = quiet
        self.logger = logger
        self.limits = limits or MessageLimits()
        self.options = {k.strip().lower(): v for k, v in (options or {}).items()}
        self.babysit = self.options.get("babysit", False)

    def get_option(self, name: str, default: Any = None, as_type: Optional[Type] = None) -> Any:
        value = self.options.get(name, default)
        return value if as_type is None else as_type(value)

    @functools.cached_property
    def scheduler_id(self) -> str:
        return type(self).__name__.lower().replace("scheduler", "")

    @functools.cached_property
    def base_command(self) -> List[str]:
        cmd = []
        if self.babysit:
            cmd += ["python3", "-m", "gator.babysitter"]
        cmd += ["python3", "-m", "gator"]
        if self.limits.warning is not None:
            cmd.append(f"--limit-warning={self.limits.warning}")
        if self.limits.error is not None:
            cmd.append(f"--limit-error={self.limits.error}")
        if self.limits.critical is not None:
            cmd.append(f"--limit-critical={self.limits.critical}")
        cmd += [
            "--parent",
            self.parent,
            "--interval",
            f"{self.interval}",
            "--scheduler",
            self.scheduler_id,
            ["--all-msg", "--quiet"][self.quiet],
        ]
        return cmd

    def create_command(self, child: Child, options: Optional[Dict[str, str]] = None) -> str:
        """
        Build a command for launching a job on the compute infrastructure using
        details from the child object.

        :param child:   Describes the task to launch
        :param options: Override options
        :returns:       String of the full command
        """
        full_opts = self.options.copy()
        full_opts.update(options or {})

        return " ".join(
            itertools.chain(
                self.base_command,
                ["--id", child.ident, "--tracking", child.tracking.as_posix()],
                *(["--sched-arg", f"{k}={v}"] for k, v in full_opts.items()),
            )
        )

    @abc.abstractmethod
    async def launch(self, tasks: List[Child]) -> None:
        """
        Launch all given tasks onto the compute infrastructure, this function is
        asynchronous but should return as soon as all tasks are launched (i.e.
        it should not block until tasks complete).

        :param tasks:   List of Child objects to schedule
        """
        return

    @abc.abstractmethod
    async def wait_for_all(self) -> None:
        """
        Wait for all tasks previously launched to complete by polling the compute
        infrastructure.
        """
        return
