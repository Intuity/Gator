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
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .db import Database
from .types import LogEntry, LogSeverity
from .ws_client import WebsocketClient


class Logger:

    FORMAT = {
        "DEBUG"  : ("[bold cyan]", "[/bold cyan]"),
        "INFO"   : ("[bold]", "[/bold]"),
        "WARNING": ("[bold amber]", "[/bold amber]"),
        "ERROR"  : ("[bold red]", "[/bold red]"),
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

    def set_console(self, console : Console) -> None:
        self.__console = console

    async def set_database(self, database : Database) -> None:
        self.__database = database
        await self.__database.register(LogEntry)
        self.__database.define_transform(LogSeverity, "INTEGER", int, LogSeverity)

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
                  timestamp : Optional[datetime] = None) -> None:
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
            prefix, suffix = self.FORMAT.get(severity.name, ("[bold]", "[/bold]"))
            self.__console.log(f"{prefix}[{severity.name:<7s}]{suffix} {message}")
        # Record to database
        if self.__database is not None:
            await self.__database.push_logentry(LogEntry(severity =severity,
                                                         message  =message,
                                                         timestamp=timestamp))
        # Tee to file if configured
        if self.__log_fh is not None:
            date = datetime.now().strftime(r"%H:%M:%S")
            self.__log_fh.write(f"[{date}] [{severity.name:<7s}] {message}\n")

    async def debug(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None) -> None:
        await self.log(LogSeverity.DEBUG, message, forward, timestamp)

    async def info(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None) -> None:
        await self.log(LogSeverity.INFO, message, forward, timestamp)

    async def warning(self,
                      message   : str,
                      forward   : Optional[bool] = None,
                      timestamp : Optional[datetime] = None) -> None:
        await self.log(LogSeverity.WARNING, message, forward, timestamp)

    async def error(self,
                    message   : str,
                    forward   : Optional[bool] = None,
                    timestamp : Optional[datetime] = None) -> None:
        await self.log(LogSeverity.ERROR, message, forward, timestamp)

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
