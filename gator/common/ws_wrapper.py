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
import itertools
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
        self.__monitor_task = None
        self.__request_lock = asyncio.Lock()
        self.__next_request_id = itertools.count()
        self.__pending_req_id = None
        self.__pending_req_evt = asyncio.Event()
        self.__pending_response = None

    @property
    def linked(self):
        return self.ws is not None

    async def start_monitor(self) -> None:
        self.__monitor_task = asyncio.create_task(self.__monitor())
        def _teardown() -> None:
            asyncio.run(self.stop())
        atexit.register(_teardown)

    async def stop_monitor(self) -> None:
        if self.__monitor_task is not None:
            self.__monitor_task.cancel()
            await self.__monitor_task
            self.__monitor_task = None

    async def __monitor(self) -> None:
        try:
            async for raw in self.ws:
                try:
                    response = json.loads(raw)
                    if "req_id" in response and response["req_id"] == self.__pending_req_id:
                        self.__pending_req_id = None
                        self.__pending_response = response
                        self.__pending_req_evt.set()
                    else:
                        print(f"Got unexpected message: {raw}")
                except json.JSONDecodeError:
                    raise WebsocketWrapperError(f"Failed to decode response from: {raw}")
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
            async with self.__request_lock:
                # For a non-posted request, setup alert for response
                if not posted:
                    self.__pending_req_id = next(self.__next_request_id)
                # Serialise and send the request
                await self.ws.send(json.dumps({ "action": key.lower(),
                                                "req_id": self.__pending_req_id or 0,
                                                "posted": posted,
                                                **kwargs }))
                # Posted requests return immediately
                if posted:
                    return None
                # Non-posted requests wait for a response
                else:
                    await self.__pending_req_evt.wait()
                    self.__pending_req_evt.clear()
                    response = self.__pending_response
                    self.__pending_response = None
                    if response.get("result", "error") != "success":
                        raise WebsocketWrapperError(f"Server responded with an "
                                                    f"error for '{key}': {response}")
                    return response

        return _shim
