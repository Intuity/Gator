import asyncio
import os
import sys
from random import choice

from gator.common.logger import Logger, LogSeverity
from gator.common.ws_client import WebsocketClient

async def emit():
    ws_cli = WebsocketClient()
    await ws_cli.start()
    log = Logger(ws_cli)
    print(f"LINKED? {log.ws_cli.linked} {os.environ.get('GATOR_PARENT', None)}")
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    for idx in range(int(sys.argv[1] if len(sys.argv) > 1 else 10)):
        await log.log(choice(list(LogSeverity)), f"This is message {prefix}{idx}")
        print(f"PRINT {prefix}{idx}")
        await asyncio.sleep(1)
    await ws_cli.stop()

asyncio.run(emit())
