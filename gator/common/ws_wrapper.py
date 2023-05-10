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
import dataclasses
import functools
import itertools
import json
from typing import Any, Dict, Optional, Union

import websockets

from .ws_router import WebsocketRouter


@dataclasses.dataclass
class WebsocketWrapperPending:
    req_id   : int
    event    : asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    response : Optional[Dict] = None

class WebsocketWrapperError(Exception):
    pass


class WebsocketWrapper(WebsocketRouter):

    def __init__(self,
                 ws : Optional[websockets.WebSocketClientProtocol] = None) -> None:
        super().__init__()
        self.ws = ws
        self.ws_event = asyncio.Event()
        self.__monitor_task = None
        self.__next_request_id = itertools.count()
        self.__request_lock = asyncio.Lock()
        self.__pending = {}

    @property
    def linked(self):
        return self.ws is not None and self.ws.open

    async def start_monitor(self) -> None:
        self.__monitor_task = asyncio.create_task(self.monitor())
        def _teardown() -> None:
            asyncio.run(self.stop_monitor())
        atexit.register(_teardown)

    async def stop_monitor(self) -> None:
        if self.__monitor_task is not None:
            self.__monitor_task.cancel()
            await self.__monitor_task
            self.__monitor_task = None

    async def send(self, data : Union[str, dict]) -> None:
        await self.ws.send(data if isinstance(data, str) else json.dumps(data))

    async def measure_latency(self) -> float:
        pong = await self.ws.ping()
        latency = await pong
        return latency

    async def monitor(self) -> None:
        try:
            async for raw in self.ws:
                try:
                    message = json.loads(raw)
                    # See if a pending request is matched
                    if (rsp_id := message.get("rsp_id", None)) is not None:
                        async with self.__request_lock:
                            if (pend := self.__pending.get(rsp_id, None)) is not None:
                                pend.response = message
                                pend.event.set()
                                del self.__pending[rsp_id]
                                continue
                    # Else, route
                    await self.route(self, message)
                except json.JSONDecodeError:
                    raise WebsocketWrapperError(f"Failed to decode message: {raw}")
        except asyncio.CancelledError:
            pass

    @functools.lru_cache()
    def __getattr__(self, key : str) -> Any:
        # Attempt to resolve
        try:
            return getattr(super(), key)
        except AttributeError:
            pass
        async def _shim(posted   : bool = False,
                        **kwargs : Dict[str, Union[str, int]]) -> Dict[str, Union[str, int]]:
            # Wait until server is available
            await self.ws_event.wait()
            if not self.ws:
                return
            # Send data to the server
            # NOTE: A lock is used to avoid multiple outstanding requests to the
            #       server at the same time
            # For a non-posted request, setup alert for response
            pending = None
            if not posted:
                async with self.__request_lock:
                    pending = WebsocketWrapperPending(next(self.__next_request_id))
                    self.__pending[pending.req_id] = pending
            # Serialise and send the request
            full_req = { "action": key.lower(), "posted": posted, "payload": kwargs }
            if not posted:
                full_req["req_id"] = pending.req_id
            await self.send(full_req)
            # Posted requests return immediately
            if posted:
                return None
            # Non-posted requests wait for a response
            else:
                await pending.event.wait()
                pending.event.clear()
                # Check for result
                if pending.response.get("result", "error") != "success":
                    raise WebsocketWrapperError(f"Server responded with an "
                                                f"error for '{key}': {pending.response}")
                # Return response
                return pending.response.get("payload", {})

        return _shim
