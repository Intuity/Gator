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
from typing import List

from ..common.child import Child
from .common import BaseScheduler

class LocalScheduler(BaseScheduler):
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self,
                 parent   : str,
                 interval : int = 5,
                 quiet    : bool = True) -> None:
        super().__init__(parent=parent, interval=interval, quiet=quiet)
        self.lock     = asyncio.Lock()
        self.launched = {}
        self.complete = {}
        self.monitors = {}

    async def __monitor(self, id : str, proc : asyncio.subprocess.Process) -> None:
        rc = await proc.wait()
        async with self.lock:
            self.complete[id] = rc
            del self.launched[id]
            del self.monitors[id]

    async def launch(self, tasks : List[Child]) -> None:
        async with self.lock:
            for child in tasks:
                self.launched[child.id] = await asyncio.create_subprocess_shell(
                    self.create_command(child),
                    stdin =asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL
                )
                self.monitors[child.id] = asyncio.create_task(self.__monitor(child.id, self.launched[child.id]))

    async def wait_for_all(self):
        await asyncio.gather(*self.monitors.values())
