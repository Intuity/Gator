import os
import socket
import subprocess
import sqlite3
import sys
import time
from collections import defaultdict
from contextlib import closing
from copy import copy
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Dict, List, Optional

import click
import plotly.graph_objects as pg
import psutil

class Wrapper:
    """ Wraps a single process and tracks logging & process statistics """

    def __init__(self,
                 *cmd     : List[str],
                 env      : Optional[Dict[str, str]] = None,
                 cwd      : Path = Path.cwd(),
                 tracking : Path = Path.cwd() / "tracking",
                 interval : int  = 5,
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
        """
        self.cmd = cmd
        self.env = env or copy(os.environ)
        self.cwd = cwd
        self.tracking = tracking
        self.interval = interval
        self.plotting = plotting
        self.proc = None
        self.code = None
        self.launch()
        self.monitor()

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

    def monitor(self) -> None:
        """ Track the logging and process statistics as the job runs """
        # STDOUT/STDERR monitoring
        def _stdio(proc, pipe, queue):
            while proc.poll() is None:
                line = pipe.readline()
                if len(line) > 0:
                    queue.put((time.time(), line.rstrip()))
        # Process stats monitor
        def _proc_stats(proc, stats_q, interval):
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
                    io_count = ps.io_counters() if hasattr(ps, "io_counters") else None
                    for child in ps.children(recursive=True):
                        nproc    += 1
                        cpu_perc += child.cpu_percent()
                        mem_stat  = child.memory_info()
                        rss      += mem_stat.rss
                        vms      += mem_stat.vms
                        if io_count is not None:
                            io_count += ps.io_counters() if hasattr(ps, "io_counters") else None
                    stats_q.put((time.time(), nproc, cpu_perc, rss, vms, io_count))
        # Create threads
        stdout_q = Queue()
        stderr_q = Queue()
        out_thread = Thread(target=_stdio, args=(self.proc, self.proc.stdout, stdout_q))
        err_thread = Thread(target=_stdio, args=(self.proc, self.proc.stderr, stderr_q))
        stats_q = Queue()
        ps_thread = Thread(target=_proc_stats, args=(self.proc, stats_q, self.interval))
        # Start threads
        out_thread.start()
        err_thread.start()
        ps_thread.start()
        # Wait for process to end
        self.tracking.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.tracking / f"{self.proc.pid}.db") as db:
            with closing(db.cursor()) as cursor:
                # Create the basic tables
                cursor.execute("CREATE TABLE log (timestamp, stderr, message)")
                cursor.execute("CREATE TABLE stats (timestamp, nproc, total_cpu, total_mem, total_vmem)")
                cursor.execute("CREATE TABLE attrs (name, value)")
                # Setup basic attributes
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("cmd",   " ".join(self.cmd)))
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("cwd",   self.cwd.as_posix()))
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("host",  socket.gethostname()))
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("pid",   str(self.proc.pid)))
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("start", str(time.time())))
            def _read_queues():
                with closing(db.cursor()) as cursor:
                    while not stdout_q.empty() or not stderr_q.empty():
                        if not stdout_q.empty() and (stdout := stdout_q.get_nowait()):
                            stamp, message = stdout
                            cursor.execute("INSERT INTO log VALUES (?, ?, ?)",
                                           (stamp, False, message))
                            print(f"STDOUT: {message}")
                        if not stderr_q.empty() and (stderr := stderr_q.get_nowait()):
                            stamp, message = stderr
                            cursor.execute("INSERT INTO log VALUES (?, ?, ?)",
                                           (stamp, True, message))
                            print(f"STDERR: {message}")
                    if not stats_q.empty() and (stats := stats_q.get_nowait()):
                        stamp, nproc, cpu, rss, vms, _io = stats
                        cursor.execute("INSERT INTO stats VALUES (?, ?, ?, ?, ?)",
                                       (stamp, nproc, cpu, rss, vms))
            # Process queues until process completes
            while (retcode := self.proc.poll()) is None:
                _read_queues()
                time.sleep(0.1)
            # Capture the return code
            self.code = retcode
            # Wait for the threads to complete
            out_thread.join()
            err_thread.join()
            ps_thread.join()
            # Flush queues
            _read_queues()
            # Write final attributes
            with closing(db.cursor()) as cursor:
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("end",  str(time.time())))
                cursor.execute("INSERT INTO attrs VALUES (?, ?)", ("exit", str(self.code)))
            # If plotting enabled, draw the plot
            if self.plotting:
                with closing(db.cursor()) as cursor:
                    req = cursor.execute("SELECT * FROM stats ORDER BY timestamp ASC")
                    series = defaultdict(list)
                    dates = []
                    for (stamp, nproc, cpu, rss, vms) in req.fetchall():
                        dates.append(datetime.fromtimestamp(stamp))
                        series["Processes"].append(nproc)
                        series["CPU %"].append(cpu)
                        series["RSS (MB)"].append(rss / (1024**3))
                        series["VMS (MB)"].append(vms / (1024**3))
                    fig = pg.Figure()
                    for key, vals in series.items():
                        fig.add_trace(pg.Scatter(x   =dates,
                                                 y   =vals,
                                                 mode="lines",
                                                 name=key))
                    fig.update_layout(title=f"Resource Usage for {self.proc.pid}",
                                      xaxis_title="Time")
                    fig.write_image(self.plotting.as_posix(), format="png")


@click.command()
@click.option("--gator-interval", default=5,    type=int, help="Polling interval")
@click.option("--gator-tracking", default=None, type=str, help="Tracking directory")
@click.option("--gator-plotting", default=None, type=str, help="Plot the results")
@click.argument("command", nargs=-1)
def launch(gator_interval, gator_tracking, gator_plotting, command):
    if len(command) == 0:
        with click.Context(launch) as ctx:
            click.echo(launch.get_help(ctx))
            sys.exit(0)
    kwargs = {}
    if gator_tracking is not None:
        kwargs["tracking"] = Path(gator_tracking)
    if gator_plotting is not None:
        kwargs["plotting"] = Path(gator_plotting)
    Wrapper(*command, **kwargs, interval=gator_interval)

if __name__ == "__main__":
    launch(prog_name="wrapper")
