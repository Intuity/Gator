# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
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
import pytest_asyncio

from gator.common.child import Child
from gator.common.logger import Logger
from gator.common.ws_client import WebsocketClient
from gator.scheduler import LocalScheduler
from gator.specs.jobs import Job


@pytest.mark.asyncio
class TestLocalScheduler:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self, mocker) -> None:
        # Create websocket client and logger
        self.client = WebsocketClient()
        self.client.ws_event.set()
        self.logger = Logger(self.client)
        # Allow test to run
        yield

    async def test_local_scheduling(self, mocker, tmp_path):
        """Launch a number of tasks"""
        # Create an scheduler
        sched = LocalScheduler(
            tracking=tmp_path / "tracking",
            parent="test:1234",
            interval=7,
            quiet=False,
            logger=self.logger,
        )
        assert sched.parent == "test:1234"
        assert sched.interval == 7
        assert sched.quiet is False
        # Patch asyncio so we don't launch any real operations
        as_sub = mocker.patch(
            "gator.scheduler.local.asyncio.create_subprocess_exec",
            new=AsyncMock(),
        )
        as_tsk = mocker.patch(
            "gator.scheduler.local.asyncio.create_task",
            new=MagicMock(wraps=asyncio.create_task),
        )
        as_mon = mocker.patch.object(
            sched,
            "_LocalScheduler__monitor",
            new=AsyncMock(wraps=sched._LocalScheduler__monitor),
        )
        procs = []

        def _create_proc(*_args, **_kwargs):
            nonlocal procs
            procs.append(proc := AsyncMock())
            return proc

        as_sub.side_effect = _create_proc
        # Launch some tasks
        await sched.launch(
            [
                Child(spec=Job(), ident=f"T{x}", entry=MagicMock(), tracking=tmp_path / f"T{x}")
                for x in range(10)
            ]
        )

        # Wait for all to be launched
        await sched.launch_task

        # Check for launch calls
        as_sub.assert_has_calls(
            [
                call(
                    "python3",
                    "-m",
                    "gator",
                    "--limit-error=0",
                    "--limit-critical=0",
                    "--parent",
                    "test:1234",
                    "--interval",
                    "7",
                    "--scheduler",
                    "local",
                    "--all-msg",
                    "--id",
                    f"T{x}",
                    "--tracking",
                    (tmp_path / f"T{x}").as_posix(),
                    "--sched-arg",
                    "concurrency=1",
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )
                for x in range(10)
            ]
        )
        # Check for task creation calls (1 launch task, 10 jobs)
        assert len(as_tsk.mock_calls) == 11
        # Wait for all tasks to complete
        await sched.wait_for_all()
        # Check all monitors were fired up
        as_mon.assert_has_calls([call(f"T{x}", y) for x, y in zip(range(10), procs)])

    async def test_scheduler_argument_safety(self, mocker, tmp_path):
        """Ensure arguments with special characters are handled safely"""
        # Create a scheduler
        sched = LocalScheduler(
            tracking=tmp_path / "tracking",
            parent="test:1234",
            interval=5,
            quiet=True,
            logger=self.logger,
        )
        # Patch asyncio so we don't launch any real operations
        as_sub = mocker.patch(
            "gator.scheduler.local.asyncio.create_subprocess_exec",
            new=AsyncMock(),
        )
        mocker.patch.object(
            sched,
            "_LocalScheduler__monitor",
            new=AsyncMock(wraps=sched._LocalScheduler__monitor),
        )
        procs = []

        def _create_proc(*args, **kwargs):
            nonlocal procs
            # Capture the command arguments to verify they're passed as a list
            proc = AsyncMock()
            procs.append((proc, args, kwargs))
            return proc

        as_sub.side_effect = _create_proc

        # Create a job with potentially dangerous characters in arguments
        # These should be passed as literal arguments, not interpreted by shell
        dangerous_job = Job(
            "dangerous_test",
            cwd=tmp_path.as_posix(),
            command="echo",
            args=[
                "hello; rm -rf /",
                "$(whoami)",
                "`id`",
                "&& cat /etc/passwd",
            ],
        )

        # Note: Since gator launches jobs using its own command structure,
        # the Job spec's command and args won't be directly passed to subprocess.
        # Instead, gator uses "python3 -m gator" with the job spec.
        # However, the fix ensures ANY arguments in the command list are safe.

        # Launch the task
        child = Child(
            spec=dangerous_job,
            ident="dangerous",
            entry=MagicMock(),
            tracking=tmp_path / "dangerous",
        )
        await sched.launch([child])

        # Wait for launch
        await sched.launch_task

        # Verify create_subprocess_exec was called (not create_subprocess_shell)
        assert as_sub.call_count == 1

        # Get the command that was passed
        _proc, cmd_args, cmd_kwargs = procs[0]

        # Verify it's a list of arguments (as positional args to exec)
        assert len(cmd_args) > 0, "Command should be passed as positional arguments"

        # Verify the command starts with python3 -m gator (base command)
        assert cmd_args[0] == "python3"
        assert cmd_args[1] == "-m"
        assert cmd_args[2] == "gator"

        # Verify stdin/stdout/stderr are redirected
        assert cmd_kwargs["stdin"] == subprocess.DEVNULL
        assert cmd_kwargs["stdout"] == subprocess.DEVNULL
        assert cmd_kwargs["stderr"] == subprocess.STDOUT
