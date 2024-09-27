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
from typing import List, Optional

from .common import BaseScheduler, SchedulerError
from ..common.child import Child
from ..common.logger import Logger
from ..specs import Job

class LocalScheduler(BaseScheduler):
    """ Executes tasks on the local machine """

    def __init__(self,
                 parent   : str,
                 interval : int = 5,
                 quiet    : bool = True,
                 logger   : Optional[Logger] = None,
                 options  : Optional[dict[str, str]] = None) -> None:
        super().__init__(parent, interval, quiet, logger, options)
        self.launch_task = None
        self.update_lock = asyncio.Lock()
        self.launched    = {}
        self.complete    = {}
        self.monitors    = {}
        self.slots       = {}
        self.concurrency = self.get_option("concurrency", 1, int)
        self.update      = asyncio.Event()
        if self.concurrency < 1:
            raise SchedulerError(f"Invalid concurrency of {self.concurrency}")

    async def __monitor(self, id : str, proc : asyncio.subprocess.Process) -> None:
        # Check to see if the process has finished, if it hasn't then wait
        if (rc := proc.returncode) is None:
            rc = await proc.wait()
        # Grab the lock
        async with self.update_lock:
            self.complete[id] = rc
            released = self.slots[id]
            self.concurrency += released
            del self.launched[id]
            del self.monitors[id]
            del self.slots[id]
            self.update.set()
        # Log how many concurrency slots were released
        await self.logger.debug(f"Task '{id}' released {released} slots on completion")

    async def launch(self, tasks : List[Child]) -> None:
        await self.logger.debug(f"Local scheduler using concurrency of {self.concurrency}")
        async def _inner():
            # Track tasks to be scheduled
            remaining = tasks[:]
            # Iterate until task queue exhausted
            while remaining:
                # Wait for some concurrency to be available
                slots = 0
                while slots < 1:
                    async with self.update_lock:
                        slots = self.concurrency
                        self.concurrency = 0
                    if slots < 1:
                        self.update.clear()
                        await self.update.wait()
                # Pop the next task
                task = remaining.pop(0)
                # Grant 1 slot for a job, up to max jobs for a group/array
                if isinstance(task.spec, Job):
                    granted = 1
                else:
                    granted = min(slots, task.spec.expected_jobs)
                slots -= granted
                # Log
                await self.logger.debug(f"Scheduling '{task.id}' with {granted} slots")
                # Get the lock again
                async with self.update_lock:
                    # Launch jobs
                    self.slots[task.id] = granted
                    self.launched[task.id] = await asyncio.create_subprocess_shell(
                        self.create_command(task, {"concurrency": granted}),
                        stdin =asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    self.monitors[task.id] = asyncio.create_task(
                        self.__monitor(task.id, self.launched[task.id])
                    )
                    # Restore any unused concurrency
                    self.concurrency += slots
        # Start background task launching
        self.launch_task = asyncio.create_task(_inner())

    async def wait_for_all(self):
        await self.launch_task
        await asyncio.gather(*self.monitors.values())
