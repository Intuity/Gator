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

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from gator.common.ws_router import WebsocketRouter

@pytest.mark.asyncio
class TestWebsocketRouter:

    async def test_root(self):
        """ Access the root path """
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Make a request without an action
        await router.route(ws, {})
        ws.send.assert_called_with(json.dumps({ "action": "identify",
                                               "tool": "gator",
                                               "version": "1.0" }))
        ws.send.reset_mock()
        # Make a posted request without an action
        await router.route(ws, {"posted": True})
        assert not ws.send.called

    async def test_sync_handler(self):
        """ Route to a synchronous function """
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Register some handlers
        h_sync = MagicMock()
        router.add_route("sync_a", h_sync.route_a)
        router.add_route("sync_b", h_sync.route_b)
        h_sync.route_a.return_value = { "word": "goodbye" }
        h_sync.route_b.return_value = { "word": "orange" }
        # Synchronous route A
        await router.route(ws, {"action": "sync_a", "payload": { "word": "hello" }})
        h_sync.route_a.assert_called_with(ws=ws, word="hello")
        h_sync.route_a.reset_mock()
        assert not h_sync.route_b.called
        ws.send.assert_called_with(json.dumps({ "action": "sync_a",
                                                "rsp_id": 0,
                                                "result": "success",
                                                "payload": { "word": "goodbye" } }))
        ws.send.reset_mock()
        # Synchronous route B (posted access)
        await router.route(ws, {"action": "sync_b", "payload": { "word": "apple" }, "posted": True})
        assert not h_sync.route_a.called
        h_sync.route_b.assert_called_with(ws=ws, word="apple")
        h_sync.route_b.reset_mock()
        assert not ws.send.called

    async def test_async_handler(self):
        """ Route to an asynchronous function """
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Register some handlers
        h_async = AsyncMock()
        router.add_route("async_a", h_async.route_a)
        router.add_route("async_b", h_async.route_b)
        h_async.route_a.return_value = { "word": "goodbye" }
        h_async.route_b.return_value = { "word": "orange" }
        # Synchronous route A
        await router.route(ws, {"action": "async_a", "payload": { "word": "hello" }})
        h_async.route_a.assert_called_with(ws=ws, word="hello")
        h_async.route_a.reset_mock()
        assert not h_async.route_b.called
        ws.send.assert_called_with(json.dumps({ "action": "async_a",
                                                "rsp_id": 0,
                                                "result": "success",
                                                "payload": { "word": "goodbye" } }))
        ws.send.reset_mock()
        # Synchronous route B (posted access)
        await router.route(ws, {"action": "async_b", "payload": { "word": "apple" }, "posted": True})
        assert not h_async.route_a.called
        h_async.route_b.assert_called_with(ws=ws, word="apple")
        h_async.route_b.reset_mock()
        assert not ws.send.called

    async def test_fallback(self):
        """ Fallback to another router if route cannot be resolved """
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Register handlers
        h_sync  = MagicMock()
        h_async = AsyncMock()
        router.add_route("sync",  h_sync.handler)
        router.add_route("async", h_async.handler)
        h_sync.handler.return_value  = { "word": "goodbye" }
        h_async.handler.return_value = { "word": "orange" }
        # Register fallback
        fallback = AsyncMock()
        router.fallback = fallback.route
        # Check sync route
        await router.route(ws, {"action": "sync", "payload": { "word": "hello"}})
        h_sync.handler.assert_called_with(ws=ws, word="hello")
        ws.send.assert_called_with(json.dumps({ "action": "sync",
                                                "rsp_id": 0,
                                                "result": "success",
                                                "payload": { "word": "goodbye" } }))
        assert not h_async.handler.called
        assert not fallback.route.called
        h_sync.handler.reset_mock()
        ws.send.reset_mock()
        # Check async route
        await router.route(ws, {"action": "async", "payload": { "word": "apple"}})
        h_async.handler.assert_called_with(ws=ws, word="apple")
        ws.send.assert_called_with(json.dumps({ "action": "async",
                                                "rsp_id": 0,
                                                "result": "success",
                                                "payload": { "word": "orange" }}))
        assert not h_sync.handler.called
        assert not fallback.route.called
        h_async.handler.reset_mock()
        ws.send.reset_mock()
        # Check fallback
        await router.route(ws, data := {"action": "other", "payload": {"word": "ostrich"}})
        fallback.route.assert_called_with(ws, data)
        assert not h_sync.handler.called
        assert not h_async.handler.called
        assert not ws.send.called

    async def test_unroutable(self):
        """ An error should be reported if the request cannot be routed """
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Register handlers
        h_sync = MagicMock()
        router.add_route("sync", h_sync.handler)
        h_sync.handler.return_value = { "word": "goodbye" }
        # Posted request should be silently dropped
        await router.route(ws, { "action" : "bad_route",
                                 "payload": { "word": "hello" },
                                 "posted" : True })
        assert not h_sync.handler.called
        assert not ws.send.called
        # Non-posted request should be replied to with an error
        await router.route(ws, { "action" : "bad_route",
                                 "payload": { "word": "hello" },
                                 "posted" : False })
        ws.send.assert_called_with(json.dumps({ "result": "error",
                                                "reason": "Unknown action 'bad_route'" }))
        assert not h_sync.handler.called

    async def test_handler_exception(self, mocker):
        """ Check that an exception incurred in a handler is reported back """
        # Patch the print function
        mk_print = mocker.patch("gator.common.ws_router.print")
        mk_sys   = mocker.patch("gator.common.ws_router.sys")
        # Create a fake websocket
        ws = AsyncMock()
        # Create a router
        router = WebsocketRouter()
        # Register handlers
        h_sync  = MagicMock()
        h_async = AsyncMock()
        router.add_route("sync",  h_sync.handler)
        router.add_route("async", h_async.handler)
        def _sync(**_):
            raise Exception("This is sync error")
        async def _async(**_):
            raise Exception("This is async error")
        h_sync.handler.side_effect  = _sync
        h_async.handler.side_effect = _async
        # Posted request should not incur a response
        for action in ("sync", "async"):
            await router.route(ws, { "action" : action, "posted" : True })
            mk_print.assert_called_with(f"Caught Exception on route {action}: This is {action} error",
                                        file=mk_sys.stderr)
            assert not ws.send.called
            mk_print.reset_mock()
        # Non-posted request should have a response
        for action in ("sync", "async"):
            await router.route(ws, { "action" : action, "posted" : False })
            mk_print.assert_called_with(f"Caught Exception on route {action}: This is {action} error",
                                        file=mk_sys.stderr)
            ws.send.assert_called_with(json.dumps({ "result": "error",
                                                    "reason": f"This is {action} error" }))
            ws.send.reset_mock()
            mk_print.reset_mock()
