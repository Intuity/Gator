import logging
import sqlite3
from collections import namedtuple
from contextlib import closing
from itertools import count
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from time import time
from typing import Any, List, Optional

from rich.logging import RichHandler

Attribute = namedtuple("Attribute", ("name", "value"))
LogEntry  = namedtuple("LogEntry",  ("time", "severity", "message"))
ProcStat  = namedtuple("ProcStat",  ("time", "nproc", "cpu", "mem", "vmem"))
Query     = namedtuple("Query",     ("id", "query"))
Response  = namedtuple("Response",  ("id", "data"))
Stop      = namedtuple("Stop",      ("timestamp", ))

class Database:

    def __init__(self, path : Path):
        self.path       = path
        self.request_q  = Queue()
        self.response_q = Queue()
        # Ensure path's parent folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Launch a thread to run the database
        self.query_id  = count()
        self.thread    = Thread(target=self.__run)
        self.thread.start()

    def stop(self):
        self.request_q.put(Stop(time()))
        self.thread.join()

    def push_attribute(self, attr : Attribute) -> None:
        assert isinstance(attr, Attribute)
        self.request_q.put(attr)

    def push_log(self, severity : str, message : str, stamp : Optional[int] = None) -> None:
        stamp = stamp or int(time())
        self.request_q.put(LogEntry(stamp, severity, message))

    def push_statistics(self, stats : ProcStat) -> None:
        assert isinstance(stats, ProcStat)
        self.request_q.put(stats)

    def query(self, query : str) -> List[Any]:
        assert isinstance(query, str)
        id = next(self.query_id)
        self.request_q.put(Query(id, query))
        response = self.response_q.get(block=True)
        assert response.id == id, f"Expected query ID '{id}', got '{response.id}'"
        return response.data

    def __run(self):
        logger = logging.Logger(name="db", level=logging.DEBUG)
        logger.addHandler(RichHandler())
        self.path.unlink(missing_ok=True)
        with sqlite3.connect(self.path.as_posix()) as db:
            # Create tables
            with closing(db.cursor()) as cursor:
                cursor.execute("CREATE TABLE attrs (name, value)")
                cursor.execute("CREATE TABLE logging (timestamp, severity, message)")
                cursor.execute("CREATE TABLE pstats (timestamp, nproc, total_cpu, total_mem, total_vmem)")
            # Monitor queues until stopped and flushed
            stop_monitor = False
            while not stop_monitor:
                req = self.request_q.get(block=True)
                with closing(db.cursor()) as cursor:
                    while True:
                        if isinstance(req, Query):
                            data = list(cursor.execute(req.query).fetchall())
                            self.response_q.put(Response(req.id, data))
                        elif isinstance(req, Attribute):
                            cursor.execute("INSERT INTO attrs VALUES (?, ?)", req)
                        elif isinstance(req, LogEntry):
                            logger.log(logging._nameToLevel.get(req.severity.upper(), "INFO"),
                                       req.message)
                            cursor.execute("INSERT INTO logging VALUES (?, ?, ?)", req)
                        elif isinstance(req, ProcStat):
                            cursor.execute("INSERT INTO pstats VALUES (?, ?, ?, ?, ?)", req)
                        elif isinstance(req, Stop):
                            stop_monitor = True
                            break
                        else:
                            logger.error(f"Bad queued request of type '{type(req).__name__}'")
                        # Attempt to dequeue next extra
                        try:
                            req = self.request_q.get_nowait()
                        except Empty:
                            break
