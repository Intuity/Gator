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
import sqlite3
from collections import namedtuple
from contextlib import closing
from datetime import datetime
from itertools import count
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from time import time
from typing import Any, Dict, List, Optional

from rich.logging import RichHandler

Attribute = namedtuple("Attribute", ("name", "value"))
LogEntry  = namedtuple("LogEntry",  ("time", "severity", "message"))
ProcStat  = namedtuple("ProcStat",  ("time", "nproc", "cpu", "mem", "vmem"))
Query     = namedtuple("Query",     ("id", "query", "parameters"))
Response  = namedtuple("Response",  ("id", "data"))
Stop      = namedtuple("Stop",      ("timestamp", ))

class Database:

    def __init__(self, path : Path, quiet : bool = False):
        self.path       = path
        self.quiet      = quiet
        self.request_q  = Queue()
        self.response_q = Queue()
        # Ensure path's parent folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Launch a thread to run the database
        self.query_id  = count()
        self.thread    = Thread(target=self.__run, args=(self.path, ))
        self.thread.start()

    def stop(self):
        self.request_q.put(Stop(time()))
        self.thread.join()

    # ==========================================================================
    # Attributes
    # ==========================================================================

    def push_attribute(self, attr : Attribute) -> None:
        assert isinstance(attr, Attribute)
        self.request_q.put(attr)

    def get_attributes(self, key_pattern : Optional[str] = None) -> List[Attribute]:
        query_str = "SELECT * FROM attrs"
        parameters = {}
        if key_pattern:
            query_str += f" WHERE name LIKE :key"
            parameters["key"] = key_pattern
        return [Attribute(*x) for x in self.query(query_str, parameters)]

    # ==========================================================================
    # Logging
    # ==========================================================================

    def push_log(self, severity : str, message : str, stamp : Optional[int] = None) -> None:
        stamp = stamp if stamp is not None else int(time())
        level = logging._nameToLevel[severity.upper()]
        self.request_q.put(LogEntry(stamp, level, message))

    def get_logs(self,
                 severity : Optional[str] = None,
                 exact_severity : bool = False,
                 message : Optional[str] = None,
                 before : Optional[int] = None,
                 after : Optional[int] = None) -> None:
        query = []
        parameters = {}
        if severity:
            query.append(f"severity {['>=', '='][exact_severity]} :severity")
            parameters["severity"] = logging._nameToLevel[severity.upper()]
        if message:
            query.append("message LIKE :message")
            parameters["message"] = message
        if before:
            query.append("timestamp < :before")
            parameters["before"] = before
        if after:
            query.append("timestamp >= :after")
            parameters["after"] = after
        query_str = "SELECT * FROM logging"
        if query:
            query_str += " WHERE " + " AND ".join(query)
        return [LogEntry(x[0], logging._levelToName[x[1]], x[2]) for x in self.query(query_str, parameters)]

    # ==========================================================================
    # Statistics
    # ==========================================================================

    def push_statistics(self, stats : ProcStat) -> None:
        assert isinstance(stats, ProcStat)
        self.request_q.put(stats)

    def get_statistics(self,
                       before : Optional[int] = None,
                       after : Optional[int] = None) -> None:
        query = []
        parameters = {}
        if before:
            query.append("timestamp < :before")
            parameters["before"] = before
        if after:
            query.append("timestamp >= :after")
            parameters["after"] = after
        query_str = "SELECT * FROM pstats"
        if query:
            query_str += " WHERE " + " AND ".join(query)
        return [ProcStat(datetime.fromtimestamp(x[0]), *x[1:]) for x in self.query(query_str, parameters)]

    # ==========================================================================
    # Raw Queries
    # ==========================================================================

    def query(self, query : str, parameters : Optional[Dict[str, Any]] = None) -> List[Any]:
        assert isinstance(query, str)
        id = next(self.query_id)
        self.request_q.put(Query(id, query, parameters or {}))
        response = self.response_q.get(block=True)
        assert response.id == id, f"Expected query ID '{id}', got '{response.id}'"
        return response.data

    # ==========================================================================
    # SQLite DB Thread
    # ==========================================================================

    def __run(self, path : Path) -> None:
        logger = logging.Logger(name="db", level=logging.DEBUG)
        logger.addHandler(RichHandler())
        path.unlink(missing_ok=True)
        with sqlite3.connect(path.as_posix()) as db:
            # Create tables
            with closing(db.cursor()) as cursor:
                cursor.execute("CREATE TABLE attrs (name TEXT, value TEXT)")
                cursor.execute("CREATE TABLE logging (timestamp INTEGER, "
                                                      "severity INTEGER, "
                                                      "message TEXT)")
                cursor.execute("CREATE TABLE pstats (timestamp INTEGER, "
                                                     "nproc INTEGER, "
                                                     "total_cpu INTEGER, "
                                                     "total_mem INTEGER, "
                                                     "total_vmem INTEGER)")
            # Monitor queues until stopped and flushed
            stop_monitor = False
            while not stop_monitor:
                req = self.request_q.get(block=True)
                with closing(db.cursor()) as cursor:
                    while True:
                        if isinstance(req, Query):
                            data = list(cursor.execute(req.query, req.parameters).fetchall())
                            self.response_q.put(Response(req.id, data))
                        elif isinstance(req, Attribute):
                            cursor.execute("INSERT INTO attrs VALUES (?, ?)", req)
                        elif isinstance(req, LogEntry):
                            if not self.quiet:
                                logger.log(req.severity, req.message)
                            cursor.execute("INSERT INTO logging VALUES (?, ?, ?)", req)
                        elif isinstance(req, ProcStat):
                            cursor.execute("INSERT INTO pstats VALUES (?, ?, ?, ?, ?)",
                                           [int(req[0].timestamp()), *req[1:]])
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
