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
import inspect
import json
import socket
from contextlib import closing
from datetime import datetime
from typing import Callable, Optional

import websockets

from .db import Database
from .logger import Logger
from ..types import LogEntry, LogSeverity


class ServerError(Exception):
    pass


class Server:
    """ Websocket server that exposes a local server with extensible routes """

    def __init__(self,
                 port : Optional[int] = None,
                 db   : Database      = None) -> None:
        self.db = db
        # Create a lock which is held until server thread starts
        self.__port     = port
        self.__port_set = asyncio.Event()
        # Gather routes
        self.__routes = {}
        # Register standard routes
        self.register("log", self.handle_log)
        # Hold a reference to the websocket
        self.__ws = None

    async def get_port(self) -> int:
        """ Return the allocated port number """
        # If no port is known, wait for the server to start and be allocated one
        if self.__port is None:
            await self.__port_set.wait()
        return self.__port

    async def get_address(self) -> str:
        """ Returns the URI of the server """
        hostname = socket.gethostname()
        assert hostname, "Blank hostname returned from socket.gethostname()"
        hostip = socket.gethostbyname(hostname)
        assert hostip, "Blank IP return from socket.gethostbyname()"
        port = await self.get_port()
        return f"{hostip}:{port}"

    # ==========================================================================
    # Route Registration
    # ==========================================================================

    def register(self, action : str, handler : Callable) -> None:
        """
        Register a handler with the websocket

        :param action:  Name of action to register with
        :param handler: Callback method when route is accessed
        """
        if not inspect.iscoroutinefunction(handler):
            raise ServerError("Attempted to register a non-asynchronous handler")
        self.__routes[action] = handler

    # ==========================================================================
    # Standard Routes
    # ==========================================================================

    async def handle_log(self,
                         timestamp : Optional[str] = None,
                         severity  : str = "INFO",
                         message   : str = "N/A",
                         **_kwargs) -> None:
        """
        Service remote logging request from a child process.

        Example: { "timestamp": 12345678, "severity": "ERROR", "message": "Hello!" }
        """
        # Generate or convert timestamp
        if timestamp is None:
            timestamp = datetime.now()
        else:
            timestamp = datetime.fromtimestamp(int(timestamp))
        severity = getattr(LogSeverity, severity.strip().upper(), LogSeverity.INFO)
        await self.db.push_logentry(LogEntry(timestamp=timestamp,
                                             severity =severity,
                                             message  =message.strip()))

    # ==========================================================================
    # Server
    # ==========================================================================

    async def start(self) -> None:
        # If no port number provided, choose a random one
        if self.__port is None:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(('', 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__port = s.getsockname()[1]
        self.__port_set.set()
        # Start an asyncio task to run the websocket in the background
        self.__ws = await websockets.serve(self.__route, "0.0.0.0", self.__port)
        # Setup teardown
        def _teardown() -> None:
            asyncio.run(self.stop())
        atexit.register(_teardown)
        # Return the address
        address = await self.get_address()
        return address

    async def stop(self) -> None:
        if self.__ws is not None:
            self.__ws.close()
            await self.__ws.wait_closed()
            self.__ws = None

    async def __route(self, ws) -> None:
        async for message in ws:
            # Attempt to decode
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                await Logger.error(f"JSON decode error: {str(e)}")
                await ws.send(json.dumps({ "result": "error",
                                           "reason": "JSON decode failed" }))
                continue
            # Check for a supported action
            action = data.get("action", None)
            if not action:
                await ws.send(json.dumps({ "tool": "gator", "version": "1.0" }))
                continue
            elif action not in self.__routes:
                await Logger.error(f"Bad route: {action}")
                await ws.send(json.dumps({ "result": "error",
                                           "reason": f"Unknown action '{action}'" }))
                continue
            else:
                try:
                    response = { "result": "success" }
                    call_rsp = await self.__routes[action](**data)
                    response.update(call_rsp or {})
                    await ws.send(json.dumps(response))
                except Exception as e:
                    await Logger.error(f"Caught exception on route {action}: {str(e)}")
                    await ws.send(json.dumps({ "result": "error",
                                               "reason": str(e) }))
