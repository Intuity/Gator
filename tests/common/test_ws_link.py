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
from datetime import datetime

import pytest
import pytest_asyncio

from gator.common.db import Database
from gator.common.ws_client import _WebsocketClient as WebsocketClient
from gator.common.ws_server import WebsocketServer
from gator.types import LogEntry, LogSeverity


@pytest.mark.asyncio
class TestWebsocketLink:

    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self, tmp_path):
        # Setup database, server, and client
        self.db = Database(tmp_path / "test.sqlite")
        await self.db.start()
        self.db.define_transform(LogSeverity, "INTEGER", lambda x: int(x), lambda x: LogSeverity(x))
        await self.db.register(LogEntry)
        self.server = WebsocketServer(db=self.db)
        await self.server.start()
        srv_address = await self.server.get_address()
        self.client = WebsocketClient(srv_address)
        await self.client.start()
        # Check for link
        assert self.client.ws_event.is_set()
        assert self.client.linked
        # Yield to start the test
        yield
        # Clean-up
        await self.client.stop()
        await self.server.stop()
        await self.db.stop()

    async def test_double_start(self) -> None:
        """ Starting client again should have no effect """
        # Normal
        await self.client.start()
        assert self.client.ws_event.is_set()
        assert self.client.linked
        # Event should always be set
        self.client.ws_event.clear()
        await self.client.start()
        assert self.client.ws_event.is_set()
        assert self.client.linked

    async def test_double_stop(self) -> None:
        """ Stopping database, server, or client twice should have no effect """
        await self.client.stop()
        await self.server.stop()
        await self.db.stop()

    async def test_link(self) -> None:
        """ Send a ping from client to server to measure latency """
        latency = await self.client.measure_latency()
        assert latency > 0

    async def test_version(self, mocker) -> None:
        """ Send an empty message, should return the version info """
        # Capture routing requests on the client side
        evt_route = asyncio.Event()
        async def _route(*_):
            nonlocal evt_route
            evt_route.set()
        mocker.patch.object(self.client, "fallback")
        self.client.fallback.side_effect = _route
        # Send the empty message
        await self.client.send({})
        # Wait for a response
        await evt_route.wait()
        # Check for the response captured
        assert self.client.fallback.mock_calls[-1].args[1] == {"action": "identify",
                                                               "tool": "gator",
                                                               "version": "1.0"}

    async def test_logging(self, mocker) -> None:
        """ Log to the server """
        # Patch the log entry function
        evt_log = asyncio.Event()
        async def _log(_):
            nonlocal evt_log
            evt_log.set()
        mocker.patch.object(self.db, "push_logentry")
        self.db.push_logentry.side_effect = _log
        # Send a logging request
        await self.client.log(timestamp=123,
                              severity="INFO",
                              message="Hi",
                              posted=True)
        # Wait for call to log function
        await evt_log.wait()
        # Check the call
        log = self.db.push_logentry.mock_calls[-1].args[0]
        assert isinstance(log, LogEntry)
        assert log.timestamp == datetime.fromtimestamp(123)
        assert log.severity is LogSeverity.INFO
        assert log.message == "Hi"
