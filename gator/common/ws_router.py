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

import inspect
import json
import sys
from typing import Any, Callable, Dict


class WebsocketRouterError(Exception):
    pass


class WebsocketRouter:

    def __init__(self) -> None:
        self.__routes = {}
        self.fallback = None

    def add_route(self, action : str, handler : Callable) -> None:
        """
        Register a handler with the websocket

        :param action:  Name of action to register with
        :param handler: Callback method when route is accessed
        """
        if not inspect.iscoroutinefunction(handler):
            raise WebsocketRouterError("Attempted to register a non-asynchronous handler")
        self.__routes[action] = handler

    async def route(self, ws : Any, data : Dict[str, Any]) -> None:
        # Check for a supported action
        action = data.get("action", None)
        posted = data.get("posted", False)
        if not action:
            if not posted:
                await ws.send(json.dumps({ "tool": "gator", "version": "1.0" }))
        elif action not in self.__routes:
            if self.fallback:
                await self.fallback(ws, data)
            else:
                import os
                print(f"Bad route: {os.getpid()} {action} - {self} - {self.__routes.keys()}", file=sys.stderr)
                if not posted:
                    await ws.send(json.dumps({ "result": "error",
                                               "reason": f"Unknown action '{action}'" }))
        else:
            try:
                call_rsp = await self.__routes[action](ws=ws, **data.get("payload", {}))
                if not posted:
                    response = { "action" : action,
                                 "rsp_id" : data.get("req_id", 0),
                                 "result" : "success",
                                 "payload": (call_rsp or {}) }
                    await ws.send(json.dumps(response))
            except Exception as e:
                print(f"Caught {type(e).__name__} on route {action}: {str(e)}", file=sys.stderr)
                if not posted:
                    await ws.send(json.dumps({ "result": "error",
                                               "reason": str(e) }))
