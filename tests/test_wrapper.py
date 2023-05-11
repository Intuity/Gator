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
import pytest_asyncio

from gator.common.logger import Logger
from gator.common.ws_client import WebsocketClient
from gator.specs import Job
from gator.wrapper import Wrapper

@pytest.mark.asyncio
class TestWrapper:

    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self) -> None:
        self.client = WebsocketClient()
        self.client.ws_event.set()
        self.logger = Logger(self.client)
        yield

    async def test_simple(self, tmp_path) -> None:
        # Define a job specification
        job = Job("test", cwd=tmp_path.as_posix(), command="echo", args=["hi"])
        # Create a wrapper
        trk_dir = tmp_path / "tracking"
        wrp = Wrapper(spec=job, client=self.client, tracking=trk_dir, logger=self.logger)
        assert wrp.spec is job
        assert wrp.tracking == trk_dir
        # Launch the job and wait for completion
        await wrp.launch()
