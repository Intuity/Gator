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

import logging
import os
import socket
import subprocess
import time
from collections import defaultdict
from copy import copy
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Dict, Optional

import plotly.graph_objects as pg
import psutil
from rich.logging import RichHandler
from tabulate import tabulate

from .common.db import Database, Query
from .hub.api import HubAPI
from .logger import Logger
from .parent import Parent
from .server import Server
from .specs import Job
from .types import Attribute, LogEntry, LogSeverity, ProcStat


class Wrapper:
    """ Wraps a single process and tracks logging & process statistics """

    def __init__(self,
                 spec     : Job,
                 tracking : Path = Path.cwd() / "tracking",
                 interval : int  = 5,
                 plotting : Optional[Path] = None,
                 quiet    : bool = False,
                 summary  : bool = False) -> None:
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
        self.proc = None
        self.code = None
        # Create a logging instance
        self.logger = logging.Logger(name="db", level=logging.DEBUG)
        self.logger.addHandler(RichHandler())
        # Setup database
        Database.define_transform(LogSeverity, "INTEGER", lambda x: int(x), lambda x: LogSeverity(x))
        self.db = Database(self.tracking / f"{os.getpid()}.db")
        def _log_cb(entry : LogEntry) -> None:
            self.logger.log(entry.severity, entry.message)
        self.db.register(LogEntry, None if self.quiet else _log_cb)
        self.db.register(Attribute)
        self.db.register(ProcStat)
        # Setup server
        self.server = Server(db=self.db)
        self.server.start()
        if Parent.linked:
            Parent.register(self.id, self.server.address)
        elif HubAPI.linked:
            HubAPI.register(self.id, self.server.address)
        # Launch the job
        self.launch()
        Logger.info(f"Wrapper '{self.id}' monitoring child PID {self.proc.pid}")
        self.monitor()
        Logger.info(f"Wrapper '{self.id}' child PID {self.proc.pid} finished")
        Parent.complete(self.id, self.code, *self.msg_counts())

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def env(self) -> Dict[str, str]:
        env = copy(self.spec.env or os.environ)
        env["GATOR_PARENT"] = self.server.address
        return env

    @property
    def cwd(self) -> Path:
        return Path((self.spec.cwd if self.spec else None) or os.getcwd())

    def launch(self) -> int:
        """
        Launch the process and pipe STDIN, STDOUT, and STDERR with line buffering

        :returns:   The process ID of the launched task
        """
        self.proc = subprocess.Popen([self.spec.command] + self.spec.args,
                                     cwd=self.cwd,
                                     env=self.env,
                                     encoding="utf-8",
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     bufsize=1,
                                     universal_newlines=True,
                                     close_fds=True)

    def msg_counts(self):
        wrn_count = self.db.get_logentry(sql_count=True, severity=int(LogSeverity.WARNING))
        err_count = self.db.get_logentry(sql_count=True, severity=Query(gte=int(LogSeverity.ERROR)))
        return wrn_count, err_count

    def monitor(self) -> None:
        """ Track the logging and process statistics as the job runs """
        # STDOUT/STDERR monitoring
        def _stdio(pipe, db, severity):
            while True:
                line = pipe.readline()
                if len(line) > 0:
                    db.push_logentry(LogEntry(severity, line.rstrip()))
        # Process stats monitor
        def _proc_stats(proc, db, interval):
            # Catch NoSuchProcess in case it exits before monitoring can start
            try:
                ps = psutil.Process(pid=proc.pid)
            except psutil.NoSuchProcess:
                return
            elapsed = 0
            while proc.poll() is None:
                # Capture statistics
                elapsed = 0
                with ps.oneshot():
                    nproc    = 1
                    cpu_perc = ps.cpu_percent()
                    mem_stat = ps.memory_info()
                    rss, vms = mem_stat.rss, mem_stat.vms
                    # io_count = ps.io_counters() if hasattr(ps, "io_counters") else None
                    for child in ps.children(recursive=True):
                        try:
                            c_cpu_perc = child.cpu_percent()
                            c_mem_stat   = child.memory_info()
                        except psutil.ZombieProcess:
                            continue
                        nproc    += 1
                        cpu_perc += c_cpu_perc
                        rss      += c_mem_stat.rss
                        vms      += c_mem_stat.vms
                        # if io_count is not None:
                        #     io_count += ps.io_counters() if hasattr(ps, "io_counters") else None
                    db.push_procstat(ProcStat(datetime.now(), nproc, cpu_perc, rss, vms))
                # Count up to the interval so that process is regularly polled
                if elapsed < interval:
                    elapsed += 1
                    time.sleep(1)
                    continue
        # Create database
        self.tracking.mkdir(parents=True, exist_ok=True)
        # Setup test attributes
        self.db.push_attribute(Attribute("cmd",   " ".join([self.spec.command] + self.spec.args)))
        self.db.push_attribute(Attribute("cwd",   self.cwd.as_posix()))
        self.db.push_attribute(Attribute("host",  socket.gethostname()))
        self.db.push_attribute(Attribute("pid",   str(self.proc.pid)))
        self.db.push_attribute(Attribute("start", str((started_at := datetime.now()).timestamp())))
        # Create threads
        out_thread = Thread(target=_stdio, args=(self.proc.stdout, self.db, LogSeverity.INFO), daemon=True)
        err_thread = Thread(target=_stdio, args=(self.proc.stderr, self.db, LogSeverity.ERROR), daemon=True)
        ps_thread = Thread(target=_proc_stats, args=(self.proc, self.db, self.interval), daemon=True)
        # Start threads
        out_thread.start()
        err_thread.start()
        ps_thread.start()
        # Wait for process to end
        last = datetime.now()
        while (retcode := self.proc.poll()) is None:
            time.sleep(0.1)
            if ((curr := datetime.now()) - last) > timedelta(seconds=1):
                Parent.update(self.id, *self.msg_counts())
                last = curr
        self.code = retcode
        # Insert final attributes
        self.db.push_attribute(Attribute("end",  str((stopped_at := datetime.now()).timestamp())))
        self.db.push_attribute(Attribute("exit", str(self.code)))
        # Pull data back from resource tracking
        data = self.db.get_procstat(sql_order_by=("timestamp", True))
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
            fig.update_layout(title=f"Resource Usage for {self.proc.pid}",
                              xaxis_title="Time")
            fig.write_image(self.plotting.as_posix(), format="png")
        # Summarise process usage
        if self.summary:
            max_nproc = max(map(lambda x: x.nproc, data)) if data else 0
            max_cpu   = max(map(lambda x: x.cpu, data)) if data else 0
            max_mem   = max(map(lambda x: x.mem, data)) if data else 0
            print(tabulate([[f"Summary of process {self.proc.pid}"],
                            ["Max Processes",           max_nproc],
                            ["Max CPU %",               f"{max_cpu * 100:.1f}"],
                            ["Max Memory Usage (MB)",   f"{max_mem / 1024**3:.2f}"],
                            ["Total Runtime (H:MM:SS)", str(stopped_at - started_at).split(".")[0]]],
                            tablefmt="simple_grid"))
