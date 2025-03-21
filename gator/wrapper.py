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
import os
import shlex
import socket
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import expandvars
import plotly.graph_objects as pg
import psutil
from tabulate import tabulate

from .common.layer import BaseLayer, MetricResponse
from .common.summary import Summary
from .common.types import Attribute, JobResult, LogSeverity, ProcStat


class Wrapper(BaseLayer):
    """Wraps a single process and tracks logging & process statistics"""

    def __init__(self, *args, plotting: bool = False, summary: bool = False, **kwargs) -> None:
        """
        Initialise the wrapper, launch it and monitor it until completion.

        :param plotting: Plot the resource usage once the job completes.
        :param summary:  Display a tabulated summary of resource usage
        """
        super().__init__(*args, **kwargs)
        self.plotting = plotting
        self.summary = summary
        self.proc = None
        # Capture forwarded messages from the wrapped job
        if self.logger:
            self.logger.capture_all = True

    async def launch(self, *args, **kwargs) -> None:
        await self.setup(*args, **kwargs)
        # Register endpoint for metrics
        self.server.add_route("metric", self.__handle_metric)
        # Register additional data types
        await self.db.register(Attribute)
        await self.db.register(ProcStat)
        # Record stop time
        self.started = self.updated = datetime.now().timestamp()
        await self.db.push_attribute(Attribute(name="started", value=str(self.started)))
        # Launch
        await self.__launch()
        # Record stop time
        self.stopped = self.updated = datetime.now().timestamp()
        await self.db.push_attribute(Attribute(name="stopped", value=str(self.stopped)))
        # Report
        await self.__report()
        # Teardown
        await self.teardown(*args, **kwargs)

    async def stop(self, **kwargs) -> None:
        await super().stop(**kwargs)
        await self.logger.warning("Stopping leaf job")
        if self.proc and not self.complete:
            try:
                top = psutil.Process(self.proc.pid)
                for child in top.children(recursive=True):
                    child.kill()
                top.kill()
            except psutil.NoSuchProcess:
                pass

    async def summarise(self) -> Summary:
        summary = await super().summarise()
        if self.result is JobResult.FAILURE:
            summary.failed_ids = [[self.spec.ident]]
        else:
            summary.failed_ids = []
        if self.started and not self.complete:
            summary.running_ids = [[self.spec.ident]]
        else:
            summary.running_ids = []
        return summary

    async def __handle_metric(self, name: str, value: int, **_) -> MetricResponse:
        """
        Handle an arbitrary metric being reported from a child, the only names
        that cannot be used are those reserved for message statistics (e.g.
        msg_debug, msg_info, etc).

        Example: { "name": "lint_warnings", "value": 12 }
        """
        self.metrics.set_own(name, value)
        # Return success
        return {"result": "success"}

    async def __monitor_stdio(
        self,
        proc: asyncio.subprocess.Process,
        stdout: asyncio.subprocess.PIPE,
        stderr: asyncio.subprocess.PIPE,
    ) -> None:
        log_fh = (self.tracking / f"raw_{proc.pid}.log").open("w", encoding="utf-8", buffering=1)
        log_lk = asyncio.Lock()

        async def _monitor(pipe, severity):
            while not pipe.at_eof():
                line = await pipe.readline()
                line = line.decode("utf-8")
                async with log_lk:
                    log_fh.write(line)
                clean = line.rstrip()
                if len(clean) > 0:
                    await self.logger.log(severity, clean)

        t_stdout = asyncio.create_task(_monitor(stdout, LogSeverity.INFO))
        t_stderr = asyncio.create_task(_monitor(stderr, LogSeverity.ERROR))
        await asyncio.gather(t_stdout, t_stderr)
        log_fh.flush()
        log_fh.close()

    async def __monitor_usage(
        self,
        proc: asyncio.subprocess.Process,
        done_evt: asyncio.Event,
        cpu_cores: int,
        memory_mb: int,
    ) -> None:
        # Catch NoSuchProcess in case it exits before monitoring can start
        try:
            ps = psutil.Process(pid=proc.pid)
        except psutil.NoSuchProcess:
            return
        # Tracks when resources exceed limits to avoid lots of messages
        exceeding = False
        # Watch the process
        while not done_evt.is_set():
            try:
                # Capture statistics
                with ps.oneshot():
                    await self.logger.debug(f"Capturing statistics for {proc.pid}")
                    nproc = 1
                    cpu_perc = ps.cpu_percent()
                    mem_stat = ps.memory_info()
                    rss, vms = mem_stat.rss, mem_stat.vms
                    # io_count = ps.io_counters() if hasattr(ps, "io_counters") else None
                    for child in ps.children(recursive=True):
                        try:
                            c_cpu_perc = child.cpu_percent()
                            c_mem_stat = child.memory_info()
                        except psutil.ZombieProcess:
                            continue
                        nproc += 1
                        cpu_perc += c_cpu_perc
                        rss += c_mem_stat.rss
                        vms += c_mem_stat.vms
                        # if io_count is not None:
                        #     io_count += ps.io_counters() if hasattr(ps, "io_counters") else None
                    # Push statistics to the database
                    await self.db.push_procstat(
                        ProcStat(
                            timestamp=datetime.now(),
                            nproc=nproc,
                            cpu=cpu_perc,
                            mem=rss,
                            vmem=vms,
                        )
                    )
                    # Check if exceeding the limits
                    now_exceeding = (cpu_cores > 0 and cpu_perc > (100 * cpu_cores)) or (
                        memory_mb > 0 and (rss / 1e6) > memory_mb
                    )
                    if now_exceeding and not exceeding:
                        await self.logger.warning(
                            f"Job has exceed it's requested resources of "
                            f"{cpu_cores} CPU cores and {memory_mb} MB of RAM - "
                            f"current usage is {cpu_perc / 100:.01f} CPU cores and "
                            f"{rss / 1E6:0.1f} MB of RAM"
                        )
                    exceeding = now_exceeding
            except psutil.NoSuchProcess:
                break
            # If process complete or done event set, break out
            if proc.returncode is not None or done_evt.is_set():
                break
            # Count up to the interval so that process is regularly polled
            try:
                await asyncio.wait_for(done_evt.wait(), timeout=self.interval)
            except asyncio.exceptions.TimeoutError:
                pass

    async def __launch(self) -> None:
        """
        Launch the process and pipe STDIN, STDOUT, and STDERR with line buffering
        """
        # Overlay any custom variables on the environment
        env = {str(k): str(v) for k, v in (self.spec.env or os.environ).items()}
        env["GATOR_PARENT"] = await self.server.get_address()
        env["PYTHONUNBUFFERED"] = "1"
        # Determine the working directory
        working_dir = Path((self.spec.cwd if self.spec else None) or Path.cwd())
        # Expand variables in the command
        command = expandvars.expand(self.spec.command, environ=env)
        args = [expandvars.expand(str(arg), environ=env) for arg in self.spec.args]
        full_cmd = shlex.join((command, *args))
        # Ensure the tracking directory exists
        self.tracking.mkdir(parents=True, exist_ok=True)
        # Pickup CPU and RAM resource requirements
        cpu_cores = self.spec.requested_cores
        memory_mb = self.spec.requested_memory
        await self.logger.debug(
            f"Task requests {cpu_cores} CPU cores and " f"{memory_mb} MB of RAM"
        )
        # Pickup license requests
        licenses = self.spec.requested_licenses
        if licenses:
            await self.logger.debug(
                "Task requests the following licenses\n"
                + tabulate(
                    list(licenses.items()),
                    ("License", "Count"),
                    tablefmt="simple_grid",
                )
            )
        # Setup initial attributes
        await self.db.push_attribute(Attribute(name="cmd", value=full_cmd))
        await self.db.push_attribute(Attribute(name="cwd", value=working_dir.as_posix()))
        await self.db.push_attribute(Attribute(name="host", value=socket.gethostname()))
        await self.db.push_attribute(Attribute(name="req_cores", value=str(cpu_cores)))
        await self.db.push_attribute(Attribute(name="req_memory", value=str(memory_mb)))
        await self.db.push_attribute(
            Attribute(
                name="req_licenses",
                value=",".join(f"{k}={v}" for k, v in licenses.items()),
            )
        )
        # Launch the process
        await self.logger.info(f"Launching task: {full_cmd}")
        try:
            self.proc = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=working_dir,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
            )
        except Exception as e:
            await self.logger.critical(f"Caught exception launching {self.ident}: {e}")
            self.complete = True
            await self.db.push_attribute(Attribute(name="pid", value="0"))
            await self.db.push_attribute(Attribute(name="exit", value=255))
            return
        # Monitor process usage
        e_done = asyncio.Event()
        t_pmon = asyncio.create_task(self.__monitor_usage(self.proc, e_done, cpu_cores, memory_mb))
        t_stdio = asyncio.create_task(
            self.__monitor_stdio(self.proc, self.proc.stdout, self.proc.stderr)
        )
        # Run until process complete & STDOUT/STDERR digested
        await asyncio.gather(self.proc.wait(), t_stdio)
        e_done.set()
        # Wait for process monitor to drain
        try:
            await asyncio.wait_for(asyncio.gather(t_pmon), timeout=5)
        except asyncio.exceptions.TimeoutError:
            await self.logger.warning("Timed out waiting for process monitor to stop")
        # Capture the exit code
        self.code = 255 if self.terminated else self.proc.returncode
        await self.logger.info(f"Task completed with return code {self.code}")
        # Insert final attributes
        await self.db.push_attribute(Attribute(name="pid", value=str(self.proc.pid)))
        await self.db.push_attribute(Attribute(name="exit", value=str(self.code)))
        # Mark complete
        self.complete = True

    async def __report(self) -> None:
        # Pull data back from resource tracking
        data = await self.db.get_procstat(sql_order_by=("timestamp", True))
        pid = await self.db.get_attribute(name="pid")
        started_at = datetime.fromtimestamp(self.started)
        stopped_at = datetime.fromtimestamp(self.stopped)
        # If plotting enabled, draw the plot
        if self.plotting:
            dates = []
            series = defaultdict(list)
            for entry in data:
                dates.append(entry.timestamp)
                series["Processes"].append(entry.nproc)
                series["CPU %"].append(entry.cpu)
                series["Memory (MB)"].append(entry.mem / (1024**3))
                series["VMemory (MB)"].append(entry.vmem / (1024**3))
            fig = pg.Figure()
            for key, vals in series.items():
                fig.add_trace(pg.Scatter(x=dates, y=vals, mode="lines", name=key))
            fig.update_layout(title=f"Resource Usage for {pid[0].value}", xaxis_title="Time")
            fig.write_image(self.plotting.as_posix(), format="png")
        # Summarise process usage
        if self.summary:
            max_nproc = max(x.nproc for x in data) if data else 0
            max_cpu = max(x.cpu for x in data) if data else 0
            max_mem = max(x.mem for x in data) if data else 0
            print(
                tabulate(
                    [
                        [f"Summary of process {pid[0].value}"],
                        ["Max Processes", max_nproc],
                        ["Max CPU %", f"{max_cpu * 100:.1f}"],
                        ["Max Memory Usage (MB)", f"{max_mem / 1024**3:.2f}"],
                        [
                            "Total Runtime (H:MM:SS)",
                            str(stopped_at - started_at).split(".")[0],
                        ],
                    ],
                    tablefmt="simple_grid",
                )
            )
