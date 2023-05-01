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
import functools
import json
from typing import Any, Dict, Optional, Union

import websockets


class WebsocketWrapperError(Exception):
    pass


class WebsocketWrapper:

    def __init__(self,
                 ws : Optional[websockets.WebSocketClientProtocol] = None) -> None:
        self.ws = ws
        self.ws_event = asyncio.Event()
        self.lock = asyncio.Lock()

    @property
    def linked(self):
        return self.ws is not None

    @functools.lru_cache()
    def __getattr__(self, key : str) -> Any:
        # Attempt to resolve
        try:
            return getattr(super(), key)
        except AttributeError:
            pass
        async def _shim(**kwargs) -> Dict[str, Union[str, int]]:
            # Wait until server is available
            await self.ws_event.wait()
            if not self.ws:
                return
            # Send data to the server
            async with self.lock:
                await self.ws.send(json.dumps({ "action": key.lower(), **kwargs }))
                try:
                    raw = await self.ws.recv()
                    response = json.loads(raw)
                    if response.get("result", "error") != "success":
                        raise WebsocketWrapperError(f"Server responded with an error for '{key}': {response}")
                    return response
                except json.JSONDecodeError:
                    raise WebsocketWrapperError(f"Failed to decode response from server for '{key}': {raw}")
        return _shim
