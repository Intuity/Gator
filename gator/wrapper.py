import os
import socket
import subprocess
import sys
import time
from collections import defaultdict
from copy import copy
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional

import click
import plotly.graph_objects as pg
import psutil

from .db import Attribute, Database, ProcStat
from .logger import Logger
from .parent import Parent
from .server import Server

class Wrapper:
    """ Wraps a single process and tracks logging & process statistics """

    def __init__(self,
                 *cmd     : List[str],
                 id       : Optional[str] = None,
                 env      : Optional[Dict[str, str]] = None,
                 cwd      : Path = Path.cwd(),
                 tracking : Path = Path.cwd() / "tracking",
                 interval : int  = 5,
                 plotting : Optional[Path] = None,
                 port     : Optional[int] = None,
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
        self.cmd = cmd
        self.id = id or os.getpid()
        self.env = env or copy(os.environ)
        self.cwd = cwd
        self.tracking = tracking
        self.interval = interval
        self.plotting = plotting
        self.proc = None
        self.code = None
        self.db = Database(self.tracking / f"{self.id}.db", quiet=quiet)
        self.server = Server(port=port, db=self.db)
        self.server.start()
        Parent.register(self.id, self.server.address)
        self.env["GATOR_PARENT"] = self.server.address
        self.launch()
        Logger.info(f"Wrapper '{self.id}' monitoring child PID {self.proc.pid}")
        self.monitor()
        Logger.info(f"Wrapper '{self.id}' child PID {self.proc.pid} finished")
        Parent.complete(self.id, self.code, *self.msg_counts())
        self.db.stop()

    def launch(self) -> int:
        """
        Launch the process and pipe STDIN, STDOUT, and STDERR with line buffering

        :returns:   The process ID of the launched task
        """
        self.proc = subprocess.Popen(self.cmd,
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
                # Count up to the interval so that process is regularly polled
                if elapsed < interval:
                    elapsed += 1
                    time.sleep(1)
                    continue
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
                    db.push_statistics(ProcStat(time.time(), nproc, cpu_perc, rss, vms))
        # Create database
        self.tracking.mkdir(parents=True, exist_ok=True)
        # Setup test attributes
        self.db.push_attribute(Attribute("cmd",   " ".join(self.cmd)))
        self.db.push_attribute(Attribute("cwd",   self.cwd.as_posix()))
        self.db.push_attribute(Attribute("host",  socket.gethostname()))
        self.db.push_attribute(Attribute("pid",   str(self.proc.pid)))
        self.db.push_attribute(Attribute("start", str(int(time.time()))))
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
        self.db.push_attribute(Attribute("end",  str(time.time())))
        self.db.push_attribute(Attribute("exit", str(self.code)))
        # If plotting enabled, draw the plot
        if self.plotting:
            series = defaultdict(list)
            dates = []
            for (stamp, nproc, cpu, rss, vms) in self.db.query("SELECT * FROM pstats ORDER BY timestamp ASC"):
                dates.append(datetime.fromtimestamp(stamp))
                series["Processes"].append(nproc)
                series["CPU %"].append(cpu)
                series["Memory (MB)"].append(rss / (1024**3))
                series["VMemory (MB)"].append(vms / (1024**3))
            fig = pg.Figure()
            for key, vals in series.items():
                fig.add_trace(pg.Scatter(x=dates, y=vals, mode="lines", name=key))
            fig.update_layout(title=f"Resource Usage for {self.proc.pid}",
                              xaxis_title="Time")
            fig.write_image(self.plotting.as_posix(), format="png")


@click.command()
@click.option("--gator-id",       default=None, type=str, help="Job identifier")
@click.option("--gator-parent",   default=None, type=str, help="Parent's server")
@click.option("--gator-port",     default=None, type=int, help="Port number for server")
@click.option("--gator-interval", default=5,    type=int, help="Polling interval")
@click.option("--gator-tracking", default=None, type=str, help="Tracking directory")
@click.option("--gator-plotting", default=None, type=str, help="Plot the results")
@click.option("--gator-quiet",    default=False, count=True, help="Silence local logging")
@click.argument("command", nargs=-1)
def launch(gator_id, gator_parent, gator_port, gator_interval, gator_tracking, gator_plotting, gator_quiet, command):
    if len(command) == 0:
        with click.Context(launch) as ctx:
            click.echo(launch.get_help(ctx))
            sys.exit(0)
    kwargs = {}
    if gator_port is not None:
        kwargs["port"] = int(gator_port)
    if gator_tracking is not None:
        kwargs["tracking"] = Path(gator_tracking)
    if gator_plotting is not None:
        kwargs["plotting"] = Path(gator_plotting)
    if gator_parent is not None:
        Parent.parent = gator_parent
    Wrapper(*command,
            **kwargs,
            id=gator_id,
            interval=gator_interval,
            quiet=gator_quiet)

if __name__ == "__main__":
    launch(prog_name="wrapper", default_map={
        f"gator_{k[6:].lower()}": v
        for k, v in os.environ.items() if k.startswith("GATOR_")
    })
