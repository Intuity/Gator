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
import atexit
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import click
from rich.console import Console

from .db import Database
from .types import LogEntry, LogSeverity
from .ws_client import WebsocketClient


class Logger:

    FORMAT = {
        LogSeverity.DEBUG   : ("[bold cyan]", "[/bold cyan]"),
        LogSeverity.INFO    : ("[bold]", "[/bold]"),
        LogSeverity.WARNING : ("[bold yellow]", "[/bold yellow]"),
        LogSeverity.ERROR   : ("[bold red]", "[/bold red]"),
        LogSeverity.CRITICAL: ("[bold white on red]", "[/bold white on red]"),
    }

    def __init__(self,
                 ws_cli    : Optional[WebsocketClient] = None,
                 verbosity : LogSeverity               = LogSeverity.INFO,
                 forward   : bool                      = True) -> None:
        # Create a client if necessary (uses an environment variable to find the parent)
        if ws_cli is None:
            self.ws_cli = WebsocketClient()
        else:
            self.ws_cli = ws_cli
        self.verbosity  : LogSeverity                = verbosity
        self.forward    : bool                       = forward
        self.__console  : Optional[Console]          = None
        self.__database : Optional[Database]         = None
        self.__log_fh   : Optional[io.TextIOWrapper] = None
        # Retain counts of different verbosity levels
        self.__counts : Dict[LogSeverity, int] = defaultdict(lambda: 0)

    def set_console(self, console : Console) -> None:
        self.__console = console

    async def set_database(self, database : Database) -> None:
        self.__database = database
        await self.__database.register(LogEntry)
        self.__database.define_transform(LogSeverity, "INTEGER", int, LogSeverity)

    def get_count(self, *severity : List[LogSeverity]) -> int:
        return sum(self.__counts[x] for x in severity)

    def __close_log_file(self) -> None:
        if self.__log_fh is not None:
            self.__log_fh.flush()
            self.__log_fh.close()
            self.__log_fh = None

    def tee_to_file(self, path : Path) -> None:
        self.__close_log_file()
        self.__log_fh = path.open(mode="w", encoding="utf-8", buffering=1)
        self.__log_fh.write(f"Log started at {datetime.now().strftime(r'%Y-%m-%d %H:%M:%S')}\n")
        atexit.register(self.__close_log_file)

    async def log(self,
                  severity  : LogSeverity,
                  message   : str,
                  forward   : Optional[bool] = None,
                  timestamp : Optional[datetime] = None,
                  forwarded : bool = False) -> None:
        """
        Distribute a log message to various endpoints based on the setup of the
        logger and the arguments provided.

        :param severity:    Severity level of the logged message
        :param message:     Text of the message being logged
        :param forward:     Whether to forward the message onto the parent layer,
                            if this is not provided then it will default to the
                            logger's forward parameter (set during construction)
        :param timestamp:   Optional timestamp that the message was produced, if
                            not provided then one will be generated
        :param forwarded:   Whether the message has been forwarded from another
                            layer, if set to True this excludes it from the
                            message counting (to avoid double counting in
                            aggregated metrics) and does not submit it to either
                            the log file or the database.
        """
        # Record the number of messages from this level
        if not forwarded:
            self.__counts[severity] += 1
        # If forward is 'None', use the default value
        forward = self.forward if forward is None else forward
        # Generate a timestamp if required
        if timestamp is None:
            timestamp = datetime.now()
        # If linked to parent and forwarding requested, push log upwards
        if forward and self.ws_cli.linked and severity >= self.verbosity:
            await self.ws_cli.log(timestamp=int(timestamp.timestamp()),
                                  severity =severity.name,
                                  message  =message,
                                  posted   =True)
        # If a console is attached, log locally
        if self.__console and severity >= self.verbosity:
            prefix, suffix = self.FORMAT.get(severity, ("[bold]", "[/bold]"))
            self.__console.log(f"{prefix}[{severity.name:<7s}]{suffix} {message}")
        # Record to database
        if not forwarded and self.__database is not None:
            await self.__database.push_logentry(LogEntry(severity =severity,
                                                         message  =message,
                                                         timestamp=timestamp))
        # Tee to file if configured
        if not forwarded and self.__log_fh is not None:
            date = datetime.now().strftime(r"%H:%M:%S")
            self.__log_fh.write(f"[{date}] [{severity.name:<7s}] {message}\n")

    async def debug(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None,
                    forwarded : bool = False) -> None:
        await self.log(LogSeverity.DEBUG, message, forward, timestamp, forwarded)

    async def info(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None,
                    forwarded : bool = False) -> None:
        await self.log(LogSeverity.INFO, message, forward, timestamp, forwarded)

    async def warning(self,
                      message   : str,
                      forward   : Optional[bool] = None,
                      timestamp : Optional[datetime] = None,
                      forwarded : bool = False) -> None:
        await self.log(LogSeverity.WARNING, message, forward, timestamp, forwarded)

    async def error(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None,
                    forwarded : bool = False) -> None:
        await self.log(LogSeverity.ERROR, message, forward, timestamp, forwarded)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    asyncio.run(Logger(verbosity=LogSeverity.DEBUG).log(
        severity=getattr(LogSeverity, severity.upper()),
        message =message
    ))

if __name__ == "__main__":
    logger(prog_name="logger")
