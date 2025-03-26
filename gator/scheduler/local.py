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
from typing import Dict, List, Optional

import websockets.exceptions

from ..common.child import Child
from ..common.logger import Logger, MessageLimits
from ..specs import Job
from .common import BaseScheduler, SchedulerError


class LocalScheduler(BaseScheduler):
    """Executes tasks on the local machine"""

    def __init__(
        self,
        parent: str,
        interval: int = 5,
        quiet: bool = True,
        logger: Optional[Logger] = None,
        options: Optional[Dict[str, str]] = None,
        limits: Optional[MessageLimits] = None,
    ) -> None:
        super().__init__(parent, interval, quiet, logger, options, limits)
        self.launch_task = None
        self.update_lock = asyncio.Lock()
        self.launched_processes = {}
        self.launched_children: Dict[str, Child] = {}
        self.complete = {}
        self.monitors = {}
        self.total_tasks = 0
        self.slots = {}
        self.concurrency = self.get_option("concurrency", 1, int)
        self.update = asyncio.Event()
        if self.concurrency < 0:
            raise SchedulerError(f"Invalid concurrency of {self.concurrency}")

    async def __monitor(self, ident: str, proc: asyncio.subprocess.Process) -> None:
        # Check to see if the process has finished, if it hasn't then wait
        if (rc := proc.returncode) is None:
            rc = await proc.wait()
        # Grab the lock
        async with self.update_lock:
            self.complete[ident] = rc
            released = self.slots[ident]
            del self.launched_processes[ident]
            del self.launched_children[ident]
            del self.monitors[ident]
            del self.slots[ident]
            # Give the released slots preferentially to running children
            released = await self.update_children_slots(released)
            # Take any remaining to schedule new jobs
            self.concurrency += released
            self.update.set()
        # Log how many concurrency slots were released
        await self.logger.debug(f"Task '{ident}' released {released} slots on completion")

    async def launch(self, tasks: List[Child]) -> None:
        await self.logger.debug(f"Local scheduler using concurrency of {self.concurrency}")
        self.total_tasks += len(tasks)

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
                await self.logger.debug(f"Scheduling '{task.ident}' with {granted} slots")
                # Get the lock again
                async with self.update_lock:
                    # Launch jobs
                    self.slots[task.ident] = granted
                    self.launched_processes[task.ident] = await asyncio.create_subprocess_shell(
                        self.create_command(task, {"concurrency": granted}),
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    self.launched_children[task.ident] = task
                    self.monitors[task.ident] = asyncio.create_task(
                        self.__monitor(task.ident, self.launched_processes[task.ident])
                    )
                    # Restore any unused concurrency
                    self.concurrency += slots

        # Start background task launching
        self.launch_task = asyncio.create_task(_inner())

    async def wait_for_all(self):
        try:
            await self.launch_task
        except asyncio.CancelledError:
            pass
        await asyncio.gather(*self.monitors.values())

    async def update_options(self, options: Dict[str, str]) -> Dict[str, str]:
        updated_options = {}

        if "concurrency" in options:
            concurrency = self.get_option("concurrency", 1, int)
            remaining = int(options["concurrency"]) - concurrency

            if remaining:
                # If any available, give the extra concurrency preferentially
                # to running children before using it to schedule more jobs
                # ourselves.
                remaining = await self.update_children_slots(remaining)
                remaining_tasks = (
                    self.total_tasks - len(self.complete) - len(self.launched_children)
                )
                granted = max(remaining, remaining_tasks)
                async with self.update_lock:
                    self.concurrency += granted
                updated_options["concurrency"] = self.options["concurrency"] = concurrency + granted
            else:
                # Unmodifed
                updated_options["concurrency"] = concurrency

        return updated_options

    async def update_children_slots(self, slots: int) -> int:
        """
        Update the concurrency for children
        """
        remaining = slots
        for ident, child in self.launched_children.items():
            if not remaining:
                break
            if isinstance(child.spec, Job):
                continue
            if child.spec.expected_jobs == self.slots[ident]:
                continue
            if child.ws is None or not child.ws.linked:
                continue
            granted = self.slots[ident] + remaining
            try:
                child_updated_opts = await child.ws.update_scheduler_opts(
                    options={"concurrency": granted}
                )
            except websockets.exceptions.ConnectionClosed:
                child_updated_opts = {}
            used = child_updated_opts.get("concurrency", self.slots[ident])
            remaining -= granted - used
            self.slots[ident] = used

        return remaining

    async def stop(self):
        if self.launch_task is not None:
            self.launch_task.cancel()
