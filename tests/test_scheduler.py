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

from unittest.mock import MagicMock, call

import gator.scheduler
from gator.scheduler import Scheduler

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
