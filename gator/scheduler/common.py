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
from typing import List

from ..common.child import Child

class BaseScheduler:
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self,
                 parent   : str,
                 interval : int = 5,
                 quiet    : bool = True) -> None:
        self.parent   = parent
        self.interval = interval
        self.quiet    = quiet

    @property
    @functools.lru_cache()
    def scheduler_id(self) -> str:
        return type(self).__name__.lower().replace("scheduler", "")

    @property
    @functools.lru_cache()
    def base_command(self) -> List[str]:
        return ["python3", "-m", "gator",
                "--parent", self.parent,
                "--interval", f"{self.interval}",
                "--scheduler", self.scheduler_id,
                ["--all-msg", "--quiet"][self.quiet]]

    def create_command(self, child : Child) -> str:
        """
        Build a command for launching a job on the compute infrastructure using
        details from the child object.

        :param child:   Describes the task to launch
        :returns:       String of the full command
        """
        return " ".join(self.base_command + ["--id", child.id,
                                             "--tracking", child.tracking.as_posix()])

    @abc.abstractmethod
    async def launch(self, tasks : List[Child]) -> None:
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
