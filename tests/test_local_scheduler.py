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
            "gator.scheduler.local.asyncio.create_subprocess_shell",
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
                    f"python3 -m gator --limit-error=0 --limit-critical=0"
                    " --parent test:1234 --interval 7 --scheduler local --all-msg "
                    "--internal "
                    f"--id T{x} --tracking {(tmp_path / f'T{x}').as_posix()}"
                    " --sched-arg concurrency=1",
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

    async def test_local_scheduler_default_launch(self, mocker, tmp_path):
        """Check that launch() without `internal` flag uses Tier/scheduler for a single Job"""
        from gator.launch import launch
        from gator.specs import JobArray

        # Patch Console to avoid output during test
        mocker.patch("gator.launch.Console")
        # Mock the Tier class to verify it's instantiated
        mk_tier_cls = mocker.patch("gator.launch.Tier")
        mk_tier = MagicMock()
        mk_tier.launch = AsyncMock()
        mk_tier.summarise = AsyncMock()
        mk_tier.is_root = True
        mk_tier_cls.return_value = mk_tier
        # Define a job specification
        job = Job("test_scheduler", cwd=tmp_path.as_posix(), command="echo", args=["scheduler"])
        # Call launch without internal flag (defaults to False)
        trk_dir = tmp_path / "tracking"
        await launch(spec=job, tracking=trk_dir, scheduler=LocalScheduler)
        # Verify Tier was instantiated
        mk_tier_cls.assert_called_once()
        call_kwargs = mk_tier_cls.call_args.kwargs
        # The single Job should be wrapped in a JobArray
        assert isinstance(call_kwargs["spec"], JobArray)
        assert len(call_kwargs["spec"].jobs) == 1
        assert call_kwargs["spec"].jobs[0] is job
        assert call_kwargs["tracking"] == trk_dir
        assert call_kwargs["scheduler"] is LocalScheduler
        # Verify Tier.launch() was called
        mk_tier.launch.assert_called_once()
        mk_tier.summarise.assert_called_once()
