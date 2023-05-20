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
import socket
from contextlib import closing
from datetime import datetime
from typing import Optional

import websockets

from .db import Database
from .logger import Logger
from .types import LogSeverity
from .ws_router import WebsocketRouter
from .ws_wrapper import WebsocketWrapper


class WebsocketServer(WebsocketRouter):
    """ Websocket server that exposes a local server with extensible routes """

    def __init__(self,
                 db     : Database,
                 logger : Logger,
                 port   : Optional[int] = None) -> None:
        super().__init__()
        # Store the database and logger pointers
        self.db = db
        self.logger = logger
        # Create a lock which is held until server thread starts
        self.__port     = port
        self.__port_set = asyncio.Event()
        # Register standard routes
        self.add_route("log", self.handle_log)
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
        # Log the message
        await self.logger.log(severity, message.strip(), timestamp=timestamp, forwarded=True)

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
        self.__ws = await websockets.serve(self.__handle_client, "0.0.0.0", self.__port)
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

    async def __handle_client(self, ws) -> None:
        wrp = WebsocketWrapper(ws)
        wrp.ws_event.set()
        wrp.fallback = self.route
        await wrp.monitor()
