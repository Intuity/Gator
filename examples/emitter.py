import asyncio
import os
from functools import wraps
from random import choice

import click

from gator.common.logger import Logger, LogSeverity
from gator.common.ws_client import WebsocketClient


def coro_command(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.command()
@click.option("--count", type=int, default=10)
@click.option("--include-errors/--exclude_errors", default=True)
@click.option("--prefix", type=str, default="")
@coro_command
async def emit(count, include_errors, prefix):
    ws_cli = WebsocketClient()
    await ws_cli.start()
    log = Logger(ws_cli)
    print(f"LINKED? {log.ws_cli.linked} {os.environ.get('GATOR_PARENT', None)}")
    severities = [s for s in LogSeverity if include_errors or s < LogSeverity.ERROR]
    for idx in range(count):
        await log.log(choice(severities), f"This is message {prefix}{idx}")
        print(f"PRINT {prefix}{idx}")
        await asyncio.sleep(1)
    await ws_cli.stop()


emit()
