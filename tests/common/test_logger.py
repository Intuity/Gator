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

import pytest

from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner

import gator.common.logger
from gator.common.logger import Logger
from gator.common.types import LogSeverity

@pytest.fixture
def logger(mocker) -> Logger:
    mock_time = mocker.patch("gator.common.logger.time")
    mock_time.time.return_value = 1234
    # Create a fake websocket interface
    ws_cli        = MagicMock()
    ws_cli.linked = False
    ws_cli.log    = AsyncMock()
    # Create a logger
    logger = Logger(ws_cli, verbosity=LogSeverity.DEBUG)
    return logger

@pytest.fixture
def logger_local(logger) -> Logger:
    logger.set_console(MagicMock())
    return logger

@pytest.fixture
def logger_linked(logger_local) -> Logger:
    logger_local.ws_cli.linked = True
    return logger_local

class TestLogger:

    @pytest.mark.asyncio
    async def test_unlinked(self, logger):
        """ Local logging goes to the console """
        # Raw
        await logger.log(LogSeverity.INFO, "Testing info")
        assert not logger.ws_cli.log.called
        # Debug
        await logger.debug("Testing debug")
        assert not logger.ws_cli.log.called
        # Info
        await logger.info("Testing info")
        assert not logger.ws_cli.log.called
        # Warning
        await logger.warning("Testing warning")
        assert not logger.ws_cli.log.called
        # Error
        await logger.error("Testing error")
        assert not logger.ws_cli.log.called

    @pytest.mark.asyncio
    async def test_local(self, logger_local):
        """ Local logging goes to the console """
        logger = logger_local
        # Raw
        await logger.log(LogSeverity.INFO, "Testing info")
        assert not logger.ws_cli.log.called
        logger.console.log.assert_called_with("[bold][INFO   ][/bold] Testing info")
        logger.console.log.reset_mock()
        # Debug
        await logger.debug("Testing debug")
        assert not logger.ws_cli.log.called
        logger.console.log.assert_called_with("[bold cyan][DEBUG  ][/bold cyan] Testing debug")
        logger.console.log.reset_mock()
        # Info
        await logger.info("Testing info")
        assert not logger.ws_cli.log.called
        logger.console.log.assert_called_with("[bold][INFO   ][/bold] Testing info")
        logger.console.log.reset_mock()
        # Warning
        await logger.warning("Testing warning")
        assert not logger.ws_cli.log.called
        logger.console.log.assert_called_with("[bold amber][WARNING][/bold amber] Testing warning")
        logger.console.log.reset_mock()
        # Error
        await logger.error("Testing error")
        assert not logger.ws_cli.log.called
        logger.console.log.assert_called_with("[bold red][ERROR  ][/bold red] Testing error")
        logger.console.log.reset_mock()

    @pytest.mark.asyncio
    async def test_linked(self, logger_linked):
        """ Local logging goes to the console """
        logger = logger_linked
        # Raw
        await logger.log(LogSeverity.INFO, "Testing info")
        assert not logger.console.log.called
        logger.ws_cli.log.assert_called_with(timestamp=1234,
                                             severity="INFO",
                                             message="Testing info",
                                             posted=True)
        logger.ws_cli.log.reset_mock()
        # Debug
        await logger.debug("Testing debug")
        assert not logger.console.log.called
        logger.ws_cli.log.assert_called_with(timestamp=1234,
                                             severity="DEBUG",
                                             message="Testing debug",
                                             posted=True)
        logger.ws_cli.log.reset_mock()
        # Info
        await logger.info("Testing info")
        assert not logger.console.log.called
        logger.ws_cli.log.assert_called_with(timestamp=1234,
                                             severity="INFO",
                                             message="Testing info",
                                             posted=True)
        logger.ws_cli.log.reset_mock()
        # Warning
        await logger.warning("Testing warning")
        assert not logger.console.log.called
        logger.ws_cli.log.assert_called_with(timestamp=1234,
                                             severity="WARNING",
                                             message="Testing warning",
                                             posted=True)
        logger.ws_cli.log.reset_mock()
        # Error
        await logger.error("Testing error")
        assert not logger.console.log.called
        logger.ws_cli.log.assert_called_with(timestamp=1234,
                                             severity="ERROR",
                                             message="Testing error",
                                             posted=True)
        logger.ws_cli.log.reset_mock()

    def test_cli(self, mocker):
        """ Log via the command line interface """
        mk_time = mocker.patch("gator.common.logger.time")
        mk_time.time.return_value = 1234
        wc_cls = mocker.patch("gator.common.logger.WebsocketClient")
        wc_cls.return_value = (ws_cli := AsyncMock())
        ws_cli.linked = True
        runner = CliRunner()
        # Default (info severity)
        runner.invoke(gator.common.logger.logger, ["This is a test"])
        ws_cli.log.assert_called_with(timestamp=1234,
                                      severity="INFO",
                                      message="This is a test",
                                      posted=True)
        ws_cli.log.reset_mock()
        # Debug
        runner.invoke(gator.common.logger.logger, ["--severity", "debug", "This is a debug test"])
        ws_cli.log.assert_called_with(timestamp=1234,
                                      severity="DEBUG",
                                      message="This is a debug test",
                                      posted=True)
        ws_cli.log.reset_mock()
        # Info
        runner.invoke(gator.common.logger.logger, ["--severity", "info", "This is an info test"])
        ws_cli.log.assert_called_with(timestamp=1234,
                                      severity="INFO",
                                      message="This is an info test",
                                      posted=True)
        ws_cli.log.reset_mock()
        # Warning
        runner.invoke(gator.common.logger.logger, ["--severity", "warning", "This is a warning test"])
        ws_cli.log.assert_called_with(timestamp=1234,
                                      severity="WARNING",
                                      message="This is a warning test",
                                      posted=True)
        ws_cli.log.reset_mock()
        # Error
        runner.invoke(gator.common.logger.logger, ["--severity", "error", "This is an error test"])
        ws_cli.log.assert_called_with(timestamp=1234,
                                      severity="ERROR",
                                      message="This is an error test",
                                      posted=True)
        ws_cli.log.reset_mock()
