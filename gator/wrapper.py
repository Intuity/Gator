import os
import socket
import subprocess
import sys
import time
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional

import click
import plotly.graph_objects as pg
import psutil
from tabulate import tabulate

from .db import Attribute, Database, ProcStat
from .job_spec import JobSpec, parse_spec
from .logger import Logger
from .parent import Parent
from .server import Server


class Wrapper:
    """ Wraps a single process and tracks logging & process statistics """

    def __init__(self,
                 spec     : JobSpec,
                 tracking : Path = Path.cwd() / "tracking",
                 interval : int  = 5,
                 plotting : Optional[Path] = None,
                 quiet    : bool = False) -> None:
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
        :param port:     Optional port number to launch the server on.
        """
        self.spec = spec
        self.tracking = tracking
        self.interval = interval
        self.plotting = plotting
        self.proc = None
        self.code = None
        self.db = Database(self.tracking / f"{self.id}.db", quiet=quiet)
        self.server = Server(port=self.spec.port, db=self.db)
        self.server.start()
        Parent.register(self.id, self.server.address)
        self.launch()
        Logger.info(f"Wrapper '{self.id}' monitoring child PID {self.proc.pid}")
        self.monitor()
        Logger.info(f"Wrapper '{self.id}' child PID {self.proc.pid} finished")
        Parent.complete(self.id, self.code, *self.msg_counts())
        self.db.stop()

    @property
    def id(self) -> str:
        return self.spec.id or f"{socket.gethostname()}_{os.getpid()}_{int(datetime.now().timestamp())}"

    @property
    def env(self) -> Dict[str, str]:
        env = copy(self.spec.env or os.environ)
        env["GATOR_PARENT"] = self.server.address
        return env

    @property
    def cwd(self) -> Path:
        return Path(self.spec.cwd or os.getcwd())

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
        wrn_count = self.db.query("SELECT COUNT(timestamp) FROM logging WHERE severity = \"WARNING\"")
        err_count = self.db.query("SELECT COUNT(timestamp) FROM logging WHERE severity = \"ERROR\"")
        return wrn_count[0][0], err_count[0][0]

    def monitor(self) -> None:
        """ Track the logging and process statistics as the job runs """
        # STDOUT/STDERR monitoring
        def _stdio(proc, pipe, db, severity):
            while proc.poll() is None:
                line = pipe.readline()
                if len(line) > 0:
                    db.push_log(severity, line.rstrip(), int(time.time()))
        # Process stats monitor
        def _proc_stats(proc, db, interval):
            ps = psutil.Process(pid=proc.pid)
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
                    db.push_statistics(ProcStat(datetime.now(), nproc, cpu_perc, rss, vms))
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
        self.db.push_attribute(Attribute("start", int((started_at := datetime.now()).timestamp())))
        # Create threads
        out_thread = Thread(target=_stdio, args=(self.proc, self.proc.stdout, self.db, "INFO"))
        err_thread = Thread(target=_stdio, args=(self.proc, self.proc.stderr, self.db, "ERROR"))
        ps_thread = Thread(target=_proc_stats, args=(self.proc, self.db, self.interval))
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
        self.db.push_attribute(Attribute("end",  int((stopped_at := datetime.now()).timestamp())))
        self.db.push_attribute(Attribute("exit", str(self.code)))
        # Pull data back from resource tracking
        data = []
        for (stamp, *other) in self.db.query("SELECT * FROM pstats ORDER BY timestamp ASC"):
            data.append(ProcStat(datetime.fromtimestamp(stamp), *other))
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
        max_nproc = max(map(lambda x: x.nproc, data))
        max_cpu   = max(map(lambda x: x.cpu, data))
        max_mem   = max(map(lambda x: x.mem, data))
        print(tabulate([[f"Summary of process {self.proc.pid}"],
                        ["Max Processes",           max_nproc],
                        ["Max CPU %",               f"{max_cpu * 100:.1f}"],
                        ["Max Memory Usage (MB)",   f"{max_mem / 1024**3:.2f}"],
                        ["Total Runtime (H:MM:SS)", str(stopped_at - started_at).split(".")[0]]],
                        tablefmt="simple_grid"))


@click.command()
@click.option("--gator-id",       default=None,  type=str, help="Job identifier")
@click.option("--gator-parent",   default=None,  type=str, help="Parent's server")
@click.option("--gator-port",     default=None,  type=int, help="Port number for server")
@click.option("--gator-interval", default=5,     type=int, help="Polling interval", show_default=True)
@click.option("--gator-tracking", default=None,  type=click.Path(), help="Tracking directory")
@click.option("--gator-plotting", default=None,  type=click.Path(), help="Plot the results")
@click.option("--gator-quiet",    default=False, count=True, help="Silence local logging")
@click.option("--gator-spec",     default=None,  type=click.Path(), help="Process specification")
@click.argument("command", nargs=-1)
def launch(gator_id,
           gator_parent,
           gator_port,
           gator_interval,
           gator_tracking,
           gator_plotting,
           gator_quiet,
           gator_spec,
           command):
    if len(command) == 0 and not gator_spec:
        with click.Context(launch) as ctx:
            click.echo(launch.get_help(ctx))
            sys.exit(0)
    kwargs = {}
    if gator_tracking is not None:
        kwargs["tracking"] = Path(gator_tracking)
    if gator_plotting is not None:
        kwargs["plotting"] = Path(gator_plotting)
    # If a job specification has been provided, parse it
    if gator_spec:
        spec = parse_spec(Path(gator_spec))
    else:
        spec = JobSpec(id=gator_id,
                       parent=gator_parent,
                       port=gator_port,
                       command=command[0],
                       args=command[1:])
    if spec.parent is not None:
        Parent.parent = spec.parent
    Wrapper(spec,
            **kwargs,
            interval=gator_interval,
            quiet=gator_quiet)

if __name__ == "__main__":
    launch(prog_name="wrapper", default_map={
        f"gator_{k[6:].lower()}": v
        for k, v in os.environ.items() if k.startswith("GATOR_")
    })
