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

import logging

from click.testing import CliRunner

import gator.logger
from gator.logger import Logger

def test_logger_unlinked(mocker):
    """ When a parent is not linked, logger should print to the screen """
    mocker.patch("gator.logger.Parent")
    mocker.patch("gator.logger.local_logger")
    gator.logger.Parent.linked = False
    # Raw
    Logger.log("INFO", "This is an info message")
    gator.logger.local_logger.log.assert_called_with(logging.INFO, "This is an info message")
    gator.logger.local_logger.log.reset_mock()
    # Debug
    Logger.debug("This is a debug message")
    gator.logger.local_logger.log.assert_called_with(logging.DEBUG, "This is a debug message")
    gator.logger.local_logger.log.reset_mock()
    # info
    Logger.info("This is an info message")
    gator.logger.local_logger.log.assert_called_with(logging.INFO, "This is an info message")
    gator.logger.local_logger.log.reset_mock()
    # Warning
    Logger.warning("This is a warning message")
    gator.logger.local_logger.log.assert_called_with(logging.WARNING, "This is a warning message")
    gator.logger.local_logger.log.reset_mock()
    # Error
    Logger.error("This is an error message")
    gator.logger.local_logger.log.assert_called_with(logging.ERROR, "This is an error message")
    gator.logger.local_logger.log.reset_mock()

def test_logger_linked(mocker):
    """ When a parent is not linked, logger should print to the screen """
    mocker.patch("gator.logger.Parent")
    mocker.patch("gator.logger.local_logger")
    mocker.patch("gator.logger.time")
    gator.logger.Parent.linked = True
    gator.logger.time.time.return_value = 12345
    # Raw
    Logger.log("INFO", "This is an info message")
    gator.logger.Parent.post.assert_called_with("log",
                                                timestamp=12345,
                                                severity ="INFO",
                                                message  ="This is an info message")
    gator.logger.Parent.post.reset_mock()
    assert not gator.logger.local_logger.log.called
    # Debug
    Logger.debug("This is a debug message")
    gator.logger.Parent.post.assert_called_with("log",
                                                timestamp=12345,
                                                severity ="DEBUG",
                                                message  ="This is a debug message")
    gator.logger.Parent.post.reset_mock()
    assert not gator.logger.local_logger.log.called
    # info
    Logger.info("This is an info message")
    gator.logger.Parent.post.assert_called_with("log",
                                                timestamp=12345,
                                                severity ="INFO",
                                                message  ="This is an info message")
    gator.logger.Parent.post.reset_mock()
    assert not gator.logger.local_logger.log.called
    # Warning
    Logger.warning("This is a warning message")
    gator.logger.Parent.post.assert_called_with("log",
                                                timestamp=12345,
                                                severity ="WARNING",
                                                message  ="This is a warning message")
    gator.logger.Parent.post.reset_mock()
    assert not gator.logger.local_logger.log.called
    # Error
    Logger.error("This is an error message")
    gator.logger.Parent.post.assert_called_with("log",
                                                timestamp=12345,
                                                severity ="ERROR",
                                                message  ="This is an error message")
    gator.logger.Parent.post.reset_mock()
    assert not gator.logger.local_logger.log.called

def test_logger_cli(mocker):
    """ Check that argumnets are passed through to logger from the CLI """
    mocker.patch("gator.logger.Logger")
    runner = CliRunner()
    # Default (info severity)
    runner.invoke(gator.logger.logger, ["This is a test"])
    gator.logger.Logger.log.assert_called_with("INFO", "This is a test")
    gator.logger.Logger.log.reset_mock()
    # Debug
    runner.invoke(gator.logger.logger, ["--severity", "debug", "This is a debug test"])
    gator.logger.Logger.log.assert_called_with("DEBUG", "This is a debug test")
    gator.logger.Logger.log.reset_mock()
    # Info
    runner.invoke(gator.logger.logger, ["--severity", "info", "This is an info test"])
    gator.logger.Logger.log.assert_called_with("INFO", "This is an info test")
    gator.logger.Logger.log.reset_mock()
    # Warning
    runner.invoke(gator.logger.logger, ["--severity", "warning", "This is a warning test"])
    gator.logger.Logger.log.assert_called_with("WARNING", "This is a warning test")
    gator.logger.Logger.log.reset_mock()
    # Warning
    runner.invoke(gator.logger.logger, ["--severity", "error", "This is an error test"])
    gator.logger.Logger.log.assert_called_with("ERROR", "This is an error test")
    gator.logger.Logger.log.reset_mock()
