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
import time
from typing import Optional

import click
from rich.console import Console

from .ws_client import _WebsocketClient, WebsocketClient


class _Logger:

    FORMAT = {
        "DEBUG"  : ("[bold cyan]", "[/bold cyan]"),
        "INFO"   : ("[bold]", "[/bold]"),
        "WARNING": ("[bold amber]", "[/bold amber]"),
        "ERROR"  : ("[bold red]", "[/bold red]"),
    }

    def __init__(self,
                 ws_cli  : _WebsocketClient,
                 console : Optional[Console] = None) -> None:
        self.ws_cli  = ws_cli
        self.console = console

    def set_console(self, console : Console) -> None:
        self.console = console

    async def log(self, severity : str, message : str) -> None:
        severity = severity.strip().upper()
        if self.ws_cli.linked:
            await self.ws_cli.log(timestamp=time.time(),
                                  severity =severity,
                                  message  =message,
                                  posted   =True)
        elif self.console:
            prefix, suffix = self.FORMAT.get(severity, ("[bold]", "[/bold]"))
            self.console.log(f"{prefix}[{severity:<7s}]{suffix} {message}")

    async def debug(self, message : str) -> None:
        await self.log("DEBUG", message)

    async def info(self, message : str) -> None:
        await self.log("INFO", message)

    async def warning(self, message : str) -> None:
        await self.log("WARNING", message)

    async def error(self, message : str) -> None:
        await self.log("ERROR", message)

Logger = _Logger(WebsocketClient)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    asyncio.run(Logger.log(severity.upper(), message))

if __name__ == "__main__":
    logger(prog_name="logger")
