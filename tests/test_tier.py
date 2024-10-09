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
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from gator.common.logger import Logger
from gator.common.ws_client import WebsocketClient
from gator.specs import Job, JobArray, JobGroup
from gator.tier import Tier


@pytest.mark.asyncio
class TestTier:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self, mocker) -> None:
        # Patch database
        self.mk_db_cls = mocker.patch("gator.common.layer.Database", new=MagicMock())
        self.mk_db = MagicMock()
        self.mk_db_cls.return_value = self.mk_db
        self.mk_db.start = AsyncMock()
        self.mk_db.stop = AsyncMock()
        self.mk_db.register = AsyncMock()
        self.mk_db.push_attribute = AsyncMock()
        self.mk_db.push_logentry = AsyncMock()
        self.mk_db.push_procstat = AsyncMock()
        self.mk_db.push_metric = AsyncMock()
        self.mk_db.get_attribute = AsyncMock()
        self.mk_db.get_logentry = AsyncMock()
        self.mk_db.get_procstat = AsyncMock()
        self.mk_db.get_metric = AsyncMock()
        self.mk_db.update_metric = AsyncMock()
        # Patch wrapper timestamping
        self.mk_wrp_dt = mocker.patch("gator.wrapper.datetime")
        self.mk_wrp_dt.now.side_effect = [datetime.fromtimestamp(x) for x in (123, 234, 345, 456)]
        # Create websocket client
        self.client = WebsocketClient()
        self.client.ws_event.set()
        # Create logger
        mk_console = MagicMock()
        mk_console.log = lambda x: print(x)
        self.logger = Logger(self.client)
        self.logger.set_console(mk_console)
        # Allow test to run
        yield

    async def test_tier_group(self, tmp_path) -> None:
        """Simple group containing just one job"""
        touch_a = tmp_path / "a.touch"
        # Define a job specification
        job = Job(
            "test",
            cwd=tmp_path.as_posix(),
            command="touch",
            args=[touch_a.as_posix()],
        )
        grp = JobGroup("group", jobs=[job])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=grp, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check tier
        assert tier.spec is grp
        assert tier.client is self.client
        assert tier.logger is self.logger
        assert tier.tracking == trk_dir
        assert tier.interval == 5
        assert not tier.quiet
        assert not tier.all_msg
        assert tier.heartbeat_cb is None
        assert not tier.complete
        assert not tier.terminated
        assert tier.scheduler is None
        assert isinstance(tier.lock, asyncio.Lock)
        assert tier.jobs_launched == {}
        assert tier.jobs_pending == {}
        assert tier.jobs_completed == {}
        assert tier.job_tasks == []
        # Check touchpoint does not exist
        assert not touch_a.exists()
        # Launch the tier and wait for completion
        await tier.launch()
        # Check state after job has run
        assert tier.scheduler is not None
        assert tier.jobs_launched == {}
        assert tier.jobs_pending == {}
        assert len(tier.jobs_completed.keys()) == 1
        assert tier.job_tasks == []
        assert tier.complete
        assert not tier.terminated
        assert tier.db is not None
        assert tier.server is not None
        # Check file exists
        assert touch_a.exists()

    async def test_tier_subgroup(self, tmp_path) -> None:
        """Nested groups with jobs at different layers"""
        # Define touch point paths
        touch_a = tmp_path / "touch.a"
        touch_b = tmp_path / "touch.b"
        touch_c = tmp_path / "touch.c"
        # Define job specification
        job_a = Job("a", command="touch", args=[touch_a.as_posix()])
        job_b = Job("b", command="touch", args=[touch_b.as_posix()])
        job_c = Job("c", command="touch", args=[touch_c.as_posix()])
        grp_low = JobGroup("low", jobs=[job_a])
        grp_mid = JobGroup("mid", jobs=[job_b, grp_low])
        grp_top = JobGroup("top", jobs=[job_c, grp_mid])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(
            spec=grp_top,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
        )
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Check that touch points don't exist
        assert not touch_a.exists()
        assert not touch_b.exists()
        assert not touch_c.exists()
        # Launch tier and wait for it to complete
        await tier.launch()
        # Check state
        assert tier.complete
        assert not tier.terminated
        # Check touch points all exists
        assert touch_a.exists()
        assert touch_b.exists()
        assert touch_c.exists()

    async def test_tier_array(self, tmp_path) -> None:
        """Execute a job array"""
        # Define an arrayed job specification
        job_n = Job(
            "n",
            command="touch",
            args=[tmp_path.as_posix() + r"/touch_${GATOR_ARRAY_INDEX}"],
        )
        array = JobArray("arr", repeats=5, jobs=[job_n])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=array, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Check that touch points don't exist
        assert not any((tmp_path / f"touch_{x}").exists() for x in range(5))
        # Launch tier and wait for it to complete
        await tier.launch()
        # Check state
        assert tier.complete
        assert not tier.terminated
        # Check that touch points exist
        assert all((tmp_path / f"touch_{x}").exists() for x in range(5))

    async def test_tier_dependencies(self, tmp_path) -> None:
        """Execute a job specification with dependencies"""
        # Define touch point paths
        touch_a = tmp_path / "touch.a"
        touch_b = tmp_path / "touch.b"
        touch_c = tmp_path / "touch.c"
        touch_d = tmp_path / "touch.d"
        # Define jobs
        job_a = Job("a", command="touch", args=[touch_a.as_posix()])
        job_b = Job("b", command="touch", args=[touch_b.as_posix()], on_fail=["a"])
        job_c = Job("c", command="touch", args=[touch_c.as_posix()], on_pass=["a"])
        job_d = Job("d", command="touch", args=[touch_d.as_posix()], on_done=["a"])
        group = JobGroup("grp", jobs=[job_a, job_b, job_c, job_d])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=group, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Check that touch points don't exist
        assert not any(x.exists() for x in (touch_a, touch_b, touch_c, touch_d))
        # Launch tier and wait for it to complete
        await tier.launch()
        # Check state
        assert tier.complete
        assert not tier.terminated
        # Check the right touch points exist
        assert all(x.exists() for x in (touch_a, touch_c, touch_d))
        assert not touch_b.exists()

    async def test_tier_terminate(self, tmp_path) -> None:
        """Terminating a job should stop immediately and de-schedule all dependencies"""
        # Define touch point paths
        touch_a = tmp_path / "touch.a"
        touch_b = tmp_path / "touch.c"
        # Define jobs
        job_a = Job("a", command="touch", args=[touch_a.as_posix()])
        job_s = Job("s", command="sleep", args=[60], on_pass=["a"])
        job_b = Job("b", command="touch", args=[touch_b.as_posix()], on_pass=["s"])
        group = JobGroup("grp", jobs=[job_a, job_s, job_b])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=group, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Check that touch points don't exist
        assert not any(x.exists() for x in (touch_a, touch_b))
        # Start the tier and wait for it to begin running
        t_launch = asyncio.create_task(tier.launch())
        while not touch_a.exists():
            await asyncio.sleep(1)
        # Give it a little time for the sleep job to start running
        await asyncio.sleep(5)
        # Terminate the tier
        await tier.stop()
        # Wait for the tier to stop
        await t_launch
        # Check state
        assert tier.complete
        assert tier.terminated
        # Check that only the first touch file exists
        assert touch_a.exists()
        assert not touch_b.exists()

    async def test_tier_missing_dep(self, tmp_path, mocker) -> None:
        """Check that a missing job dependency is captured"""
        # Patch the logger
        mk_log = mocker.patch.object(self.logger, "error", new=AsyncMock())
        # Define jobs
        job_a = Job("a", command="sleep", args=[1])
        job_b = Job("b", command="sleep", args=[1], on_done=["a"])
        job_c = Job("c", command="sleep", args=[1], on_done=["a", "x"])
        group = JobGroup("grp", jobs=[job_a, job_b, job_c])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=group, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Run the tier
        await tier.launch()
        # Check state
        assert tier.complete
        assert tier.terminated
        # Check error logged
        mk_log.assert_any_call(
            "Could not resolve dependency 'x' of job 'c', so job can never be launched"
        )

    async def test_tier_circular_dep(self, tmp_path, mocker) -> None:
        """Check that a job dependencing on itself is captured"""
        # Patch the logger
        mk_log = mocker.patch.object(self.logger, "error", new=AsyncMock())
        # Define jobs
        job_a = Job("a", command="sleep", args=[1])
        job_b = Job("b", command="sleep", args=[1], on_done=["a"])
        job_c = Job("c", command="sleep", args=[1], on_done=["a", "c"])
        group = JobGroup("grp", jobs=[job_a, job_b, job_c])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=group, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Run the tier
        await tier.launch()
        # Check state
        assert tier.complete
        assert tier.terminated
        # Check error logged
        mk_log.assert_any_call("Cannot schedule job 'c' as it depends on itself")

    async def test_tier_dependency_on_fail(self, tmp_path, mocker) -> None:
        """Check that the right job is run in the event of a failure"""
        # Patch the logger
        mk_log = mocker.patch.object(self.logger, "warning", new=AsyncMock())
        # Define touch point paths
        touch_a = tmp_path / "touch.a"
        touch_b = tmp_path / "touch.b"
        touch_c = tmp_path / "touch.c"
        touch_d = tmp_path / "touch.d"
        # Define jobs
        job_x = Job("x", command="exit", args=[1])
        job_y = Job("y", command="exit", args=[0])
        job_a = Job("a", command="touch", args=[touch_a.as_posix()], on_pass=["x"])
        job_b = Job("b", command="touch", args=[touch_b.as_posix()], on_fail=["x"])
        job_c = Job("c", command="touch", args=[touch_c.as_posix()], on_pass=["y"])
        job_d = Job("d", command="touch", args=[touch_d.as_posix()], on_fail=["y"])
        group = JobGroup("grp", jobs=[job_x, job_y, job_a, job_b, job_c, job_d])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(spec=group, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check state
        assert not tier.complete
        assert not tier.terminated
        # Check that touch points don't exist
        assert not any(x.exists() for x in (touch_a, touch_b, touch_c, touch_d))
        # Launch tier and wait for it to complete
        await tier.launch()
        # Check state
        assert tier.complete
        assert not tier.terminated
        # Check the right touch points exist
        assert not any(x.exists() for x in (touch_a, touch_d))
        assert all(x.exists() for x in (touch_b, touch_c))
        # Check for warnings
        mk_log.assert_any_call("Dependency 'x' failed so Job 'a' will be pruned")
        mk_log.assert_any_call("Dependency 'y' passed so Job 'd' will be pruned")

    async def test_tier_get_tree(self, tmp_path) -> None:
        """Report the tree structure of a running tier"""
        # Define touch point paths
        touch_a = tmp_path / "a.touch"
        touch_b = tmp_path / "b.touch"
        touch_c = tmp_path / "c.touch"
        # Create scripts
        script_a = tmp_path / "a.sh"
        script_b = tmp_path / "b.sh"
        script_c = tmp_path / "c.sh"
        script_a.write_text(f"touch {touch_a.as_posix()}\nsleep 30\n")
        script_b.write_text(f"touch {touch_b.as_posix()}\nsleep 30\n")
        script_c.write_text(f"touch {touch_c.as_posix()}\nsleep 30\n")
        # Define job specification
        job_a = Job("a", command="sh", args=[script_a.as_posix()])
        job_b = Job("b", command="sh", args=[script_b.as_posix()])
        job_c = Job("c", command="sh", args=[script_c.as_posix()])
        grp_low = JobGroup("low", jobs=[job_a])
        grp_mid = JobGroup("mid", jobs=[job_b, grp_low])
        grp_top = JobGroup("top", jobs=[job_c, grp_mid])
        # Create a tier
        trk_dir = tmp_path / "tracking"
        tier = Tier(
            spec=grp_top,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
        )
        # Let the tier start
        t_launch = asyncio.create_task(tier.launch())
        # Wait for the touch files to appear
        while not all(x.exists() for x in (touch_a, touch_b, touch_c)):
            await asyncio.sleep(1)
        # List immediate children
        ws_cli = WebsocketClient(address=await tier.server.get_address())
        await ws_cli.start()
        response = await ws_cli.children()
        assert set(response["launched"].keys()) == {"c", "mid"}
        # Report the tree structure
        tree = await tier.get_tree()
        assert tree == {
            "c": "STARTED",
            "mid": {"b": "STARTED", "low": {"a": "STARTED"}},
        }
        # Stop the jobs
        await tier.stop()
        # Wait for the jobs to stop
        await t_launch
