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
import os
import socket
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import expandvars
import plotly.graph_objects as pg
import psutil
from tabulate import tabulate

from .common.client import Client
from .common.db import Database, Query
from .common.server import Server
from .hub.api import HubAPI
from .common.logger import Logger
from .specs import Job
from .types import Attribute, LogEntry, LogSeverity, ProcStat


class Wrapper:
    """ Wraps a single process and tracks logging & process statistics """

    def __init__(self,
                 spec     : Job,
                 tracking : Path = Path.cwd() / "tracking",
                 interval : int  = 5,
                 quiet    : bool = False,
                 summary  : bool = False,
                 plotting : Optional[Path] = None) -> None:
        """
        Initialise the wrapper, launch it and monitor it until completion.

        :param *cmd:     Command line to execute (process and arguments)
        :param env:      Modified environment to pass to the job, if no value is
                         provided then the current environment is replicated.
        :param cwd:      Set the initial working directory, if no value is
                         provided then the current working path is replicated.
        :param tracking: Path to directory to store tracking files, if no
                         directory is given then a 'tracking' directory will be
                         created in the current working path.
        :param interval: Specify the interval to record process statistics, the
                         more frequent the higher the resource usage of the
                         wrapper process will be. Defaults to 5 seconds.
        :param plotting: Plot the resource usage once the job completes.
        :param summary:  Display a tabulated summary of resource usage
        """
        self.spec = spec
        self.tracking = tracking
        self.interval = interval
        self.plotting = plotting
        self.quiet = quiet
        self.summary = summary
        self.code = None
        self.db = None
        self.server = None
        self.client = None

    @classmethod
    async def create(cls, *args, **kwargs) -> None:
        self = cls(*args, **kwargs)
        # Setup database
        Database.define_transform(LogSeverity, "INTEGER", lambda x: int(x), lambda x: LogSeverity(x))
        self.db = Database(self.tracking / f"{os.getpid()}.sqlite")
        async def _log_cb(entry : LogEntry) -> None:
            await Logger.log(entry.severity.name, entry.message)
        await self.db.start()
        await self.db.register(LogEntry, None if self.quiet else _log_cb)
        await self.db.register(Attribute)
        await self.db.register(ProcStat)
        # Setup server
        self.server = Server(db=self.db)
        server_address = await self.server.start()
        # If an immediate parent is known, register with it
        self.client = await Client.instance().start()
        await self.client.register(id=self.id, server=server_address)
        # Otherwise, if a hub is known register to it
        if HubAPI.linked:
            HubAPI.register(self.id, server_address)
        # Launch
        await self.__launch()
        # Report
        await self.__report()
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()
        # Shutdown the client
        await self.client.stop()

    @property
    def id(self) -> str:
        return self.spec.id

    async def count_messages(self):
        wrn_count = await self.db.get_logentry(sql_count=True, severity=int(LogSeverity.WARNING))
        err_count = await self.db.get_logentry(sql_count=True, severity=Query(gte=int(LogSeverity.ERROR)))
        return wrn_count, err_count

    async def __monitor_stdio(self,
                              pipe     : asyncio.subprocess.PIPE,
                              severity : LogSeverity) -> None:
        while not pipe.at_eof():
            line = await pipe.readline()
            line = line.decode("utf-8").rstrip()
            if len(line) > 0:
                await self.db.push_logentry(LogEntry(severity=severity,
                                                     message =line))

    async def __monitor_usage(self,
                              proc     : asyncio.subprocess.Process,
                              done_evt : asyncio.Event) -> None:
        # Catch NoSuchProcess in case it exits before monitoring can start
        try:
            ps = psutil.Process(pid=proc.pid)
        except psutil.NoSuchProcess:
            return
        while not done_evt.is_set():
            try:
                # Capture statistics
                with ps.oneshot():
                    await Logger.debug(f"Capturing statistics for {proc.pid}")
                    nproc    = 1
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
                        nproc    += 1
                        cpu_perc += c_cpu_perc
                        rss      += c_mem_stat.rss
                        vms      += c_mem_stat.vms
                        # if io_count is not None:
                        #     io_count += ps.io_counters() if hasattr(ps, "io_counters") else None
                    await self.db.push_procstat(ProcStat(datetime.now(), nproc, cpu_perc, rss, vms))
            except psutil.NoSuchProcess:
                break
            # Count up to the interval so that process is regularly polled
            await asyncio.sleep(self.interval)

    async def __heartbeat(self, done_evt : asyncio.Event) -> None:
        while not done_evt.is_set():
            num_wrn, num_err = await self.count_messages()
            await self.client.update(id        =self.id,
                                     warnings  =num_wrn,
                                     errors    =num_err,
                                     sub_total =1,
                                     sub_active=1)
            await asyncio.sleep(1)

    async def __launch(self) -> int:
        """
        Launch the process and pipe STDIN, STDOUT, and STDERR with line buffering

        :returns:   The process ID of the launched task
        """
        # Overlay any custom variables on the environment
        env = { str(k): str(v) for k, v in (self.spec.env or os.environ).items() }
        env["GATOR_PARENT"] = await self.server.get_address()
        # Determine the working directory
        working_dir = Path((self.spec.cwd if self.spec else None) or os.getcwd())
        # Expand variables in the command
        all_args = [str(x) for x in ([self.spec.command] + self.spec.args)]
        full_cmd = " ".join(expandvars.expand(x, environ=env) for x in all_args)
        # Setup initial attributes
        await self.db.push_attribute(Attribute(name="cmd",     value=full_cmd))
        await self.db.push_attribute(Attribute(name="cwd",     value=working_dir.as_posix()))
        await self.db.push_attribute(Attribute(name="host",    value=socket.gethostname()))
        await self.db.push_attribute(Attribute(name="started", value=str(datetime.now().timestamp())))
        # Launch the process
        await Logger.info(f"Launching task: {full_cmd}")
        proc = await asyncio.create_subprocess_shell(full_cmd,
                                                     cwd=working_dir,
                                                     env=env,
                                                     stdin=subprocess.PIPE,
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE,
                                                     close_fds=True)
        # Capture STDOUT and STDERR
        t_stdout = asyncio.create_task(self.__monitor_stdio(proc.stdout, LogSeverity.INFO))
        t_stderr = asyncio.create_task(self.__monitor_stdio(proc.stderr, LogSeverity.ERROR))
        # Monitor process usage
        e_done = asyncio.Event()
        t_pmon = asyncio.create_task(self.__monitor_usage(proc, e_done))
        # Deliver heartbeat to the server
        t_beat = asyncio.create_task(self.__heartbeat(e_done))
        # Run until process complete & STDOUT/STDERR digested
        await Logger.info("Monitoring task")
        await asyncio.gather(proc.wait(), t_stdout, t_stderr)
        e_done.set()
        await asyncio.gather(t_pmon, t_beat)
        # Capture the exit code
        self.code = proc.returncode
        await Logger.info(f"Task completed with return code {self.code}")
        # Insert final attributes
        await self.db.push_attribute(Attribute(name="pid",     value=str(proc.pid)))
        await self.db.push_attribute(Attribute(name="stopped", value=str(datetime.now().timestamp())))
        await self.db.push_attribute(Attribute(name="exit",    value=str(self.code)))
        # Count messages
        num_wrn, num_err = await self.count_messages()
        await Logger.info(f"Recorded {num_wrn} warnings and {num_err} errors")
        # Mark job complete
        passed = (num_err == 0) and (self.code == 0)
        await self.client.complete(id        =self.id,
                                   code      =self.code,
                                   warnings  =num_wrn,
                                   errors    =num_err,
                                   sub_total =1,
                                   sub_passed=[0, 1][passed],
                                   sub_failed=[1, 0][passed])

    async def __report(self) -> None:
        # Pull data back from resource tracking
        data       = await self.db.get_procstat(sql_order_by=("timestamp", True))
        pid        = await self.db.get_attribute(name="pid")
        ts_started = await self.db.get_attribute(name="started")
        ts_stopped = await self.db.get_attribute(name="stopped")
        started_at = datetime.fromtimestamp(float(ts_started[0].value))
        stopped_at = datetime.fromtimestamp(float(ts_stopped[0].value))
        # If plotting enabled, draw the plot
        if self.plotting:
            dates = []
            series = defaultdict(list)
            for entry in data:
                dates.append(entry.time)
                series["Processes"].append(entry.nproc)
                series["CPU %"].append(entry.cpu)
                series["Memory (MB)"].append(entry.mem / (1024**3))
                series["VMemory (MB)"].append(entry.vmem / (1024**3))
            fig = pg.Figure()
            for key, vals in series.items():
                fig.add_trace(pg.Scatter(x=dates, y=vals, mode="lines", name=key))
            fig.update_layout(title=f"Resource Usage for {pid[0].value}",
                              xaxis_title="Time")
            fig.write_image(self.plotting.as_posix(), format="png")
        # Summarise process usage
        if self.summary:
            max_nproc = max(map(lambda x: x.nproc, data)) if data else 0
            max_cpu   = max(map(lambda x: x.cpu, data)) if data else 0
            max_mem   = max(map(lambda x: x.mem, data)) if data else 0
            print(tabulate([[f"Summary of process {pid[0].value}"],
                            ["Max Processes",           max_nproc],
                            ["Max CPU %",               f"{max_cpu * 100:.1f}"],
                            ["Max Memory Usage (MB)",   f"{max_mem / 1024**3:.2f}"],
                            ["Total Runtime (H:MM:SS)", str(stopped_at - started_at).split(".")[0]]],
                            tablefmt="simple_grid"))
