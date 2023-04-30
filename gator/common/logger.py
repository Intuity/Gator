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
import logging
import os
import time

import click
from rich.console import Console

from .client import Client

local_console = Console(log_path=False)

class Logger:

    FORMAT = {
        "DEBUG"  : ("[bold cyan]", "[/bold cyan]"),
        "INFO"   : ("[bold]", "[/bold]"),
        "WARNING": ("[bold amber]", "[/bold amber]"),
        "ERROR"  : ("[bold red]", "[/bold red]"),
    }

    @staticmethod
    async def log(severity : str, message : str) -> None:
        severity = severity.strip().upper()
        if Client.instance().linked:
            await Client.instance().log(timestamp=time.time(),
                                        severity =severity,
                                        message  =message)
        else:
            prefix, suffix = Logger.FORMAT.get(severity, ("[bold]", "[/bold]"))
            local_console.log(f"{prefix}[{severity:<7s}]{suffix} {message}")

    @staticmethod
    async def debug(message : str) -> None:
        await Logger.log("DEBUG", message)

    @staticmethod
    async def info(message : str) -> None:
        await Logger.log("INFO", message)

    @staticmethod
    async def warning(message : str) -> None:
        await Logger.log("WARNING", message)

    @staticmethod
    async def error(message : str) -> None:
        await Logger.log("ERROR", message)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    asyncio.run(Logger.log(severity.upper(), message))

if __name__ == "__main__":
    logger(prog_name="logger")
