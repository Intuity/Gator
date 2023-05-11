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
import os
from typing import Optional

import websockets

from .ws_wrapper import WebsocketWrapper


class WebsocketClient(WebsocketWrapper):

    def __init__(self, address : Optional[str] = None) -> None:
        super().__init__()
        if address is None and "GATOR_SERVER" in os.environ:
            address = os.environ["GATOR_SERVER"]
        self.address = address

    async def start(self) -> None:
        # If no address provided or websocket already started, just return
        if (self.address is None) or self.linked:
            if not self.ws_event.is_set():
                self.ws_event.set()
            return self
        # Start an asyncio task to run the websocket in the background
        self.ws = await websockets.connect(f"ws://{self.address}")
        self.ws_event.set()
        # Setup teardown
        def _teardown() -> None:
            asyncio.run(self.stop())
        atexit.register(_teardown)
        # Start socket monitor
        await self.start_monitor()
        # For chaining
        return self

    async def stop(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            await self.stop_monitor()
            self.ws = None
