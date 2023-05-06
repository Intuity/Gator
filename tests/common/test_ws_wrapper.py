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
import json
from unittest.mock import AsyncMock

import pytest

from gator.common.ws_wrapper import (WebsocketWrapper,
                                     WebsocketWrapperError,
                                     WebsocketWrapperPending)

@pytest.fixture
def wrapper() -> WebsocketWrapper:
    ws  = AsyncMock()
    wrp = WebsocketWrapper(ws)
    wrp.ws_event.set()
    return wrp

@pytest.mark.asyncio
class TestWebsocketWrapper:

    async def test_unlinked(self):
        """ An unlinked wrapper should silently drop requests """
        wrp = WebsocketWrapper()
        wrp.ws_event.set()
        assert not wrp.linked
        await wrp.some_route(word="hello", name="fred")
        assert not wrp._WebsocketWrapper__pending

    async def test_posted(self, wrapper):
        """ Send posted requests which will return immediately """
        assert wrapper.linked
        await wrapper.some_route(word="hello", name="fred", posted=True)
        wrapper.ws.send.assert_called_with(json.dumps({ "action" : "some_route",
                                                        "posted" : True,
                                                        "payload": { "word": "hello",
                                                                     "name": "fred" }}))
        assert not wrapper._WebsocketWrapper__pending

    async def test_non_posted(self, wrapper):
        """ Send non-posted requests """
        # Generate request
        response = None
        async def _cap_response():
            nonlocal response
            response = await wrapper.some_route(word="hello", name="fred")
        t_send = asyncio.create_task(_cap_response())
        # Allow the async action to complete
        while True:
            async with wrapper._WebsocketWrapper__request_lock:
                if 0 in wrapper._WebsocketWrapper__pending:
                    break
            await asyncio.sleep(0.01)
        wrapper._WebsocketWrapper__pending[0].event.set()
        wrapper._WebsocketWrapper__pending[0].response = { "result" : "success",
                                                           "action" : "some_route",
                                                           "rsp_id" : 0,
                                                           "payload": { "combo": "hello fred" }}
        await t_send
        # Check what's happened
        wrapper.ws.send.assert_called_with(json.dumps({ "action" : "some_route",
                                                        "posted" : False,
                                                        "payload": { "word": "hello",
                                                                     "name": "fred" },
                                                        "req_id" : 0 }))
        # Check the response
        assert response == { "combo": "hello fred" }

    async def test_failure(self, wrapper):
        """ Exception should be raised when result is not success """
        # Generate request
        exception = None
        async def _cap_response():
            nonlocal exception
            with pytest.raises(WebsocketWrapperError) as exception:
                await wrapper.some_route(word="hello", name="fred")
        t_send = asyncio.create_task(_cap_response())
        # Allow the async action to complete
        while True:
            async with wrapper._WebsocketWrapper__request_lock:
                if 0 in wrapper._WebsocketWrapper__pending:
                    break
            await asyncio.sleep(0.01)
        wrapper._WebsocketWrapper__pending[0].event.set()
        response = { "result" : "error",
                     "action" : "some_route",
                     "rsp_id" : 0,
                     "payload": { "combo": "hello fred" }}
        wrapper._WebsocketWrapper__pending[0].response = response
        await t_send
        # Check what's happened
        wrapper.ws.send.assert_called_with(json.dumps({ "action" : "some_route",
                                                        "posted" : False,
                                                        "payload": { "word": "hello",
                                                                     "name": "fred" },
                                                        "req_id" : 0 }))
        # Check the exception
        assert isinstance(exception.value, WebsocketWrapperError)
        assert str(exception.value) == f"Server responded with an error for 'some_route': {response}"

    async def test_monitor_fallback(self, wrapper, mocker):
        """ Check that the monitor routes messages to the fallback handler """
        # Replace the websocket with a queue so it can be iterated
        ws_q = asyncio.Queue()
        async def _ws_generator():
            nonlocal ws_q
            while True:
                try:
                    yield await asyncio.wait_for(ws_q.get(), 1)
                except asyncio.exceptions.TimeoutError:
                    break
        mocker.patch.object(wrapper, "ws", new=_ws_generator())
        # Start the monitor
        await wrapper.start_monitor()
        # Patch the fallback routing method
        mk_async = AsyncMock()
        mk_route = mocker.patch.object(wrapper, "route", new=mk_async.route)
        ev_route = asyncio.Event()
        async def _route(_ws, _msg):
            nonlocal ev_route
            ev_route.set()
        mk_route.side_effect = _route
        # Check that an unsolicited response uses the fallback
        message = { "action" : "some_route",
                    "rsp_id" : 123,
                    "payload": { "word": "hello" } }
        await ws_q.put(json.dumps(message))
        # Wait for routing to happen
        await ev_route.wait()
        ev_route.clear()
        # Check what was routed
        mk_route.assert_called_with(wrapper, message)
        mk_route.reset_mock()
        # Check that an unsolicited message uses the fallback
        message = { "action" : "other_route",
                    "payload": { "word": "hello" } }
        await ws_q.put(json.dumps(message))
        # Wait for routing to happen
        await ev_route.wait()
        ev_route.clear()
        # Check what was routed
        mk_route.assert_called_with(wrapper, message)
        mk_route.reset_mock()
        # Stop the monitor
        await wrapper.stop_monitor()

    async def test_monitor_pending(self, wrapper, mocker):
        """ Check that the monitor identifies pending messages """
        # Replace the websocket with a queue so it can be iterated
        ws_q = asyncio.Queue()
        async def _ws_generator():
            nonlocal ws_q
            while True:
                try:
                    yield await asyncio.wait_for(ws_q.get(), 1)
                except asyncio.exceptions.TimeoutError:
                    break
        mocker.patch.object(wrapper, "ws", new=_ws_generator())
        # Start the monitor
        await wrapper.start_monitor()
        # Patch the fallback routing method
        mk_async = AsyncMock()
        mk_route = mocker.patch.object(wrapper, "route", new=mk_async.route)
        # Setup a pending item
        wrapper._WebsocketWrapper__pending[123] = (pend := WebsocketWrapperPending(123))
        # Check that an unsolicited response uses the fallback
        message = { "action" : "some_route",
                    "rsp_id" : 123,
                    "payload": { "word": "hello" } }
        await ws_q.put(json.dumps(message))
        # Wait for routing to happen
        await pend.event.wait()
        assert 123 not in wrapper._WebsocketWrapper__pending
        assert pend.response == message
        # Check what was routed
        assert not mk_route.called
        # Stop the monitor
        await wrapper.stop_monitor()
