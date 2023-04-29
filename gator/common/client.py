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
import functools
import json
import os
from typing import Any, Dict, Optional, Union

import websockets


class ClientError(Exception):
    pass


class Client:

    INSTANCE = None

    def __init__(self, address : Optional[str] = None) -> None:
        if address is None and "GATOR_SERVER" in os.environ:
            address = os.environ["GATOR_SERVER"]
        self.address = address
        self.__ws = None
        self.__ws_event = asyncio.Event()
        self.__lock = asyncio.Lock()
        Client.INSTANCE = self

    @classmethod
    def instance(cls) -> "Client":
        if not cls.INSTANCE:
            cls()
        return cls.INSTANCE

    @property
    def linked(self):
        return self.__ws is not None

    async def start(self) -> None:
        # If no address provided or client already started, just return
        if (self.address is None) or (self.__ws is not None):
            if not self.__ws_event.is_set():
                self.__ws_event.set()
            return self
        # Start an asyncio task to run the websocket in the background
        self.__ws = await websockets.connect(f"ws://{self.address}")
        self.__ws_event.set()
        # Setup teardown
        def _teardown() -> None:
            asyncio.run(self.stop())
        atexit.register(_teardown)
        # For chaining
        return self

    async def stop(self) -> None:
        if self.__ws is not None:
            await self.__ws.close()
            self.__ws = None

    @functools.lru_cache()
    def __getattr__(self, key : str) -> Any:
        # Attempt to resolve
        try:
            return getattr(super(), key)
        except AttributeError:
            pass
        async def _shim(**kwargs) -> Dict[str, Union[str, int]]:
            # Wait until server is available
            await self.__ws_event.wait()
            if not self.__ws:
                return
            # Send data to the server
            async with self.__lock:
                await self.__ws.send(json.dumps({ "action": key.lower(), **kwargs }))
                try:
                    raw = await self.__ws.recv()
                    response = json.loads(raw)
                    if response.get("result", "error") != "success":
                        raise ClientError(f"Server responded with an error for '{key}': {response}")
                    return response
                except json.JSONDecodeError:
                    raise ClientError(f"Failed to decode response from server for '{key}': {raw}")
        return _shim
