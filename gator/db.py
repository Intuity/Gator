import logging
import sqlite3
import time
from collections import namedtuple
from contextlib import closing
from pathlib import Path
from queue import Queue, Empty
from threading import Thread

Attribute = namedtuple("Attribute", ("name", "value"))
LogEntry  = namedtuple("LogEntry",  ("time", "severity", "message"))
ProcStat  = namedtuple("ProcStat",  ("time", "nproc", "cpu", "mem", "vmem"))

class Database:

    INTERVAL = 0.05

    def __init__(self, path : Path):
        self.path      = path
        self.attrs_q   = Queue()
        self.logging_q = Queue()
        self.pstats_q  = Queue()
        # Launch a thread to run the database
        self.stop_flag = False
        self.thread    = Thread(target=self.__run)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        self.thread.join()

    def push_attribute(self, attr : Attribute) -> None:
        self.attrs_q.put(attr)

    def push_log(self, entry : LogEntry) -> None:
        self.logging_q.put(entry)

    def push_statistics(self, stats : ProcStat) -> None:
        self.pstats_q.put(stats)

    def __run(self):
        logger = logging.Logger(name="db", level=logging.DEBUG)
        logger.addHandler(logging.StreamHandler())
        with sqlite3.connect(self.path.as_posix()) as db:
            # Create tables
            with closing(db.cursor()) as cursor:
                cursor.execute("CREATE TABLE attrs (name, value)")
                cursor.execute("CREATE TABLE logging (timestamp, severity, message)")
                cursor.execute("CREATE TABLE pstats (timestamp, nproc, total_cpu, total_mem, total_vmem)")
            # Monitor queues until stopped and flushed
            def _all_empty():
                return self.attrs_q.empty() and self.logging_q.empty() and self.pstats_q.empty()
            while not self.stop_flag or not _all_empty():
                # If queues are empty, sleep for a bit
                if _all_empty():
                    time.sleep(self.INTERVAL)
                    continue
                # Digest any entries
                with closing(db.cursor()) as cursor:
                    # Attributes
                    try:
                        while entry := self.attrs_q.get_nowait():
                            cursor.execute("INSERT INTO attrs VALUES (?, ?)", entry)
                    except Empty:
                        pass
                    # Logging
                    try:
                        while entry := self.logging_q.get_nowait():
                            logger.log(logging._nameToLevel.get(entry.severity.upper(), "INFO"), f"[{entry.time}] {entry.message}")
                            cursor.execute("INSERT INTO logging VALUES (?, ?, ?)", entry)
                    except Empty:
                        pass
                    # Process Statistics
                    try:
                        while entry := self.pstats_q.get_nowait():
                            cursor.execute("INSERT INTO pstats VALUES (?, ?, ?, ?, ?)", entry)
                    except Empty:
                        pass
