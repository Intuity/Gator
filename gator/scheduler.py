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
import subprocess
from pathlib import Path
from typing import List, Tuple

class Scheduler:
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self,
                 parent   : str,
                 interval : int = 5,
                 quiet    : bool = True) -> None:
        self.parent   = parent
        self.interval = interval
        self.quiet    = quiet
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

    async def launch(self, tasks : List[Tuple[str, Path]]) -> None:
        common = ["python3", "-m", "gator",
                  "--parent", self.parent,
                  "--interval", f"{self.interval}",
                  ["--all-msg", "--quiet"][self.quiet]]
        async with self.lock:
            for task, trk_dir in tasks:
                self.launched[task] = await asyncio.create_subprocess_shell(
                    " ".join(common + ["--id", f"{task}", "--tracking", trk_dir.as_posix()]),
                    stdin =subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL
                )
                self.monitors[task] = asyncio.create_task(self.__monitor(task, self.launched[task]))

    async def wait_for_all(self):
        await asyncio.gather(*self.monitors.values())
