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
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from gator.scheduler import Scheduler

@pytest.mark.asyncio
class TestScheduler:

    async def test_scheduling(self, mocker):
        """ Launch a number of tasks """
        # Create an scheduler
        sched = Scheduler(parent="test:1234", interval=7, quiet=False)
        assert sched.parent == "test:1234"
        assert sched.interval == 7
        assert sched.quiet == False
        # Patch asyncio so we don't launch any real operations
        as_sub = mocker.patch("gator.scheduler.asyncio.create_subprocess_shell", new=AsyncMock())
        as_tsk = mocker.patch("gator.scheduler.asyncio.create_task", new=MagicMock(wraps=asyncio.create_task))
        as_mon = mocker.patch.object(sched,
                                     "_Scheduler__monitor",
                                     new=AsyncMock(wraps=sched._Scheduler__monitor))
        procs = []
        def _create_proc(*_args, **_kwargs):
            nonlocal procs
            procs.append(proc := AsyncMock())
            return proc
        as_sub.side_effect = _create_proc
        # Launch some tasks
        await sched.launch([f"T{x}" for x in range(10)])
        # Check for launch calls
        as_sub.assert_has_calls([
            call(f"python3 -m gator --parent test:1234 --interval 7 --all-msg --id T{x}",
                 stdin =subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL)
            for x in range(10)
        ])
        # Check for task creation calls
        assert len(as_tsk.mock_calls) == 10
        # Wait for all tasks to complete
        await sched.wait_for_all()
        # Check all monitors were fired up
        as_mon.assert_has_calls([
            call(f"T{x}", y) for x, y in zip(range(10), procs)
        ])


# def test_scheduler(mocker):
#     """ Test the basic local scheduler """
#     mocker.patch("gator.scheduler.subprocess")
#     procs = []
#     def create_proc(*args, **kwargs):
#         nonlocal procs
#         procs.append(proc := MagicMock())
#         proc.wait.return_value = True
#         return proc
#     gator.scheduler.subprocess.Popen.side_effect = create_proc
#     # Create a scheduler
#     sched = Scheduler([f"task_{x}" for x in range(10)],
#                       "localhost:1234",
#                       interval=9)
#     assert sched.tasks == [f"task_{x}" for x in range(10)]
#     assert sched.parent == "localhost:1234"
#     assert sched.interval == 9
#     # Check that all tasks are launched
#     calls = [
#         call(["python3", "-m", "gator",
#               "--parent", "localhost:1234",
#               "--quiet",
#               "--interval", "9",
#               "--id", f"task_{x}"],
#               stdin =gator.scheduler.subprocess.DEVNULL,
#               stdout=gator.scheduler.subprocess.DEVNULL)
#         for x in range(10)
#     ]
#     gator.scheduler.subprocess.Popen.assert_has_calls(calls)
#     # Wait for completions
#     sched.wait_for_all()
#     assert all([x.wait.called for x in procs])
