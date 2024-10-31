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
import socket
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from gator.common.layer import WebsocketClient
from gator.common.logger import Logger
from gator.common.types import Attribute, LogSeverity, ProcStat
from gator.specs import Cores, Job, License, Memory
from gator.wrapper import Wrapper


@pytest.mark.asyncio
class TestWrapper:
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
        # Create websocket client and logger
        self.client = WebsocketClient()
        self.client.ws_event.set()
        self.logger = Logger(self.client)
        # Allow test to run
        yield

    async def test_wrapper_basic(self, tmp_path) -> None:
        # Define a job specification
        job = Job(
            "test",
            cwd=tmp_path.as_posix(),
            command="echo",
            args=["hi"],
            resources=[
                Cores(2),
                License("A", 1),
                License("B", 3),
                Memory(1.5, "GB"),
            ],
        )
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(spec=job, client=self.client, tracking=trk_dir, logger=self.logger)
        # Check wrapper
        assert wrp.spec is job
        assert wrp.client is self.client
        assert wrp.logger is self.logger
        assert wrp.tracking == trk_dir
        assert wrp.interval == 5
        assert not wrp.quiet
        assert not wrp.all_msg
        assert wrp.heartbeat_cb is None
        assert not wrp.plotting
        assert not wrp.summary
        assert wrp.proc is None
        assert not wrp.complete
        assert not wrp.terminated
        assert wrp.code == 0
        with pytest.raises(AttributeError):
            assert wrp.db is None
        with pytest.raises(AttributeError):
            assert wrp.server is None
        # Launch the job and wait for completion
        await wrp.launch()
        # Check state after job has run
        assert wrp.proc is not None
        assert wrp.complete
        assert not wrp.terminated
        assert wrp.code == wrp.proc.returncode
        assert wrp.db is not None
        assert wrp.server is not None
        # Check Attribute, and ProcStat registered
        self.mk_db.register.assert_any_call(Attribute)
        self.mk_db.register.assert_any_call(ProcStat)
        # Check attributes pushed into the database
        values = {}
        for idx, (key, val) in enumerate(
            (
                ("ident", "test"),
                ("uidx", "0"),
                ("root", "0"),
                ("path", ""),
                ("started", None),
                ("cmd", "echo hi"),
                ("cwd", tmp_path.as_posix()),
                ("host", socket.gethostname()),
                ("req_cores", "2"),
                ("req_memory", "1500.0"),
                ("req_licenses", "A=1,B=3"),
                ("pid", str(wrp.proc.pid)),
                ("exit", str(wrp.proc.returncode)),
                ("stopped", None),
            )
        ):
            assert self.mk_db.push_attribute.mock_calls[idx].args[0].name == key
            if key in ("started", "stopped"):
                values[key] = self.mk_db.push_attribute.mock_calls[idx].args[0].value
            else:
                assert self.mk_db.push_attribute.mock_calls[idx].args[0].value == val
        # Check started
        assert int(float(values["started"])) == 123
        # Stopped can vary depending if procstat captured
        assert int(float(values["stopped"])) in (234, 345)
        # Check the 'hi' was captured
        mcs = self.mk_db.push_logentry.mock_calls
        assert any(
            (x.args[0].severity is LogSeverity.INFO and x.args[0].message == "hi") for x in mcs
        )
        # Check metrics were pushed into the database
        # NOTE: Don't check the value because the object is reused
        metrics = [x.args[0] for x in self.mk_db.push_metric.mock_calls]
        assert {x.name for x in metrics} >= {f"msg_{x.name.lower()}" for x in LogSeverity}
        # Check for update calls
        final = {}
        for call in self.mk_db.update_metric.mock_calls:
            mtc = call.args[0]
            assert mtc in metrics
            if mtc.value > final.get(mtc.name, 0):
                final[mtc.name] = mtc.value
        assert set(final.keys()) >= {"msg_info", "msg_debug"}
        assert final["msg_info"] > 0
        assert final["msg_debug"] > 0

    async def test_wrapper_procstat(self, tmp_path) -> None:
        """Check that process statistics are captured at regular intervals"""
        # Mock datetime to always return one value
        self.mk_wrp_dt.now.side_effect = None
        self.mk_wrp_dt.now.return_value = datetime.fromtimestamp(12345)
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="sleep", args=[5])
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(
            spec=job,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
            interval=1,
        )
        # Run the job
        await wrp.launch()
        # Check for a bunch of proc stat pushes
        ps = [x.args[0] for x in self.mk_db.push_procstat.mock_calls]
        assert len(ps) >= 3 and len(ps) <= 7
        assert {x.timestamp for x in ps} == {datetime.fromtimestamp(12345)}
        assert all((x.nproc >= 1) for x in ps), str([x.nproc for x in ps])
        assert all((x.cpu >= 0) for x in ps), str([x.cpu for x in ps])
        assert all((x.mem >= 0) for x in ps), str([x.mem for x in ps])
        assert all((x.vmem >= 0) for x in ps), str([x.vmem for x in ps])

    async def test_wrapper_procstat_tree(self, tmp_path):
        """Check that process statistics track children too"""
        # Mock datetime to always return one value
        self.mk_wrp_dt.now.side_effect = None
        self.mk_wrp_dt.now.return_value = datetime.fromtimestamp(12345)
        # Create a chain of simple test scripts
        for idx in range(5):
            script = tmp_path / f"script_{idx}.sh"
            lines = ["sleep 2"]
            if idx > 0:
                inner = tmp_path / f"script_{idx-1}.sh"
                lines.append(f"sh {inner.as_posix()}")
            script.write_text("\n".join(lines) + "\n")
            script.chmod(0o777)
        # Define a job specification
        job = Job(
            "test",
            cwd=tmp_path.as_posix(),
            command="sh",
            args=[script.as_posix()],
        )
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(
            spec=job,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
            interval=1,
        )
        # Run the job
        await wrp.launch()
        # Check for a bunch of proc stat pushes
        ps = [x.args[0] for x in self.mk_db.push_procstat.mock_calls]
        assert len(ps) >= 10
        assert {x.timestamp for x in ps} == {datetime.fromtimestamp(12345)}
        assert all((x.nproc >= 1) for x in ps), str([x.nproc for x in ps])
        assert any((x.nproc >= 6) for x in ps), str([x.nproc for x in ps])
        assert all((x.cpu >= 0) for x in ps), str([x.cpu for x in ps])
        assert all((x.mem >= 0) for x in ps), str([x.mem for x in ps])
        assert all((x.vmem >= 0) for x in ps), str([x.vmem for x in ps])

    async def test_wrapper_terminate(self, tmp_path) -> None:
        """Terminate a long running job partway through"""
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="sleep", args=[60])
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(spec=job, client=self.client, tracking=trk_dir, logger=self.logger)
        # Capture the start time
        starting = datetime.now()
        # Launch in background
        t_launch = asyncio.create_task(wrp.launch())
        # Wait for the job to start
        while wrp.proc is None:
            await asyncio.sleep(1)
        # Allow the job to run for a little
        await asyncio.sleep(2)
        # Check the job is still running
        assert wrp.proc is not None
        assert not wrp.complete
        assert not wrp.terminated
        # Terminate the job
        await wrp.stop()
        # Check the runtime
        assert (datetime.now() - starting).total_seconds() < 10
        # Wait for the cleanup
        await t_launch
        # Check completion marker is set
        assert wrp.complete
        assert wrp.terminated
        assert wrp.code == 255
        # Attempting to terminate again should have no effect
        await wrp.stop()
        assert wrp.complete
        assert wrp.terminated
        assert wrp.code == 255

    async def test_wrapper_plotting(self, tmp_path) -> None:
        """Check a plot is drawn if requested"""
        # Mock datetime to always return one value
        self.mk_wrp_dt.now.side_effect = None
        self.mk_wrp_dt.now.return_value = datetime.fromtimestamp(12345)
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="echo", args=["hi"])
        # Mock procstats returned by DB
        self.mk_db.get_procstat.return_value = [
            ProcStat(db_uid=0, nproc=1, cpu=0.1, mem=11 * (1024**3))
        ] * 5
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        plt_path = tmp_path / "plot.png"
        wrp = Wrapper(
            spec=job,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
            interval=1,
            plotting=plt_path,
        )
        # Check no plot exists
        assert not plt_path.exists()
        # Run the job
        await wrp.launch()
        # Check plot has been written out
        assert plt_path.exists()

    async def test_wrapper_summary(self, tmp_path, mocker) -> None:
        """Check that a process summary table is produced"""
        # Patch tabulate and print
        mocker.patch("gator.wrapper.print")
        mk_tbl = mocker.patch("gator.wrapper.tabulate")
        # Mock procstats returned by DB
        self.mk_db.get_procstat.return_value = [
            ProcStat(db_uid=0, nproc=1, cpu=0.1, mem=11 * (1024**3))
        ]

        # Mock attributes returned by the DB
        def _get_attr(name) -> Attribute:
            values = {"pid": "1000", "started": "123", "stopped": 234}
            return [Attribute(name=name, value=values.get(name, "0"))]

        self.mk_db.get_attribute.side_effect = _get_attr
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="echo", args=["hi"])
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(
            spec=job,
            client=self.client,
            tracking=trk_dir,
            logger=self.logger,
            interval=1,
            summary=True,
        )
        # Run the job
        await wrp.launch()
        # Check a tabulate call has been made
        assert mk_tbl.called
        call = mk_tbl.mock_calls[0]
        assert call.args[0][0] == ["Summary of process 1000"]
        assert call.args[0][1] == ["Max Processes", 1]
        assert call.args[0][2] == ["Max CPU %", "10.0"]
        assert call.args[0][3] == ["Max Memory Usage (MB)", "11.00"]
        assert call.args[0][4][0] == "Total Runtime (H:MM:SS)"
        # NOTE: Second part of runtime is a timedelta - difficult to mock
        assert call.kwargs["tablefmt"] == "simple_grid"

    async def test_wrapper_metric(self, tmp_path, mocker) -> None:
        """Check that metrics can be recorded and aggregated"""
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="sleep", args=[60])
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(spec=job, client=self.client, tracking=trk_dir, logger=self.logger)
        # Run the job
        t_wrp = asyncio.create_task(wrp.launch())
        # Wait for process to be created
        while wrp.proc is None:
            await asyncio.sleep(0.1)
        # Attach a client as if it's the job
        sub_cli = WebsocketClient(await wrp.server.get_address())
        await sub_cli.start()
        # Push up some metrics
        await sub_cli.metric(name="widgets", value=123)
        await sub_cli.metric(name="gizmos", value=345)
        await sub_cli.metric(name="gadgets", value=567)
        # Heartbeat to sync
        await wrp.heartbeat()
        # Check for those metrics
        assert wrp.metrics.get_own("widgets") == 123
        assert wrp.metrics.get_own("gizmos") == 345
        assert wrp.metrics.get_own("gadgets") == 567
        # Check they've been written to the database
        assert any(
            (x.args[0].name == "widgets" and x.args[0].value == 123)
            for x in self.mk_db.push_metric.mock_calls
        )
        assert any(
            (x.args[0].name == "gizmos" and x.args[0].value == 345)
            for x in self.mk_db.push_metric.mock_calls
        )
        assert any(
            (x.args[0].name == "gadgets" and x.args[0].value == 567)
            for x in self.mk_db.push_metric.mock_calls
        )
        # Update some metrics
        await sub_cli.metric(name="widgets", value=678)
        await sub_cli.metric(name="gizmos", value=789)
        await sub_cli.metric(name="gadgets", value=890)
        # Heartbeat to sync
        await wrp.heartbeat()
        # Check for those metrics
        assert wrp.metrics.get_own("widgets") == 678
        assert wrp.metrics.get_own("gizmos") == 789
        assert wrp.metrics.get_own("gadgets") == 890
        # Check they've been written to the database
        assert any(
            (x.args[0].name == "widgets" and x.args[0].value == 678)
            for x in self.mk_db.update_metric.mock_calls
        )
        assert any(
            (x.args[0].name == "gizmos" and x.args[0].value == 789)
            for x in self.mk_db.update_metric.mock_calls
        )
        assert any(
            (x.args[0].name == "gadgets" and x.args[0].value == 890)
            for x in self.mk_db.update_metric.mock_calls
        )
        # Check that the metrics are included in the summary
        summary = await wrp.summarise()
        assert summary["metrics"]["widgets"] == 678
        assert summary["metrics"]["gizmos"] == 789
        assert summary["metrics"]["gadgets"] == 890
        # Stop the client
        await sub_cli.stop()
        # Stop the job
        await wrp.stop()
        # Wait for task to complete
        await t_wrp
