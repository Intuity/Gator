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
import time

import click
from rich.logging import RichHandler

from .parent import Parent

local_logger = logging.Logger(name="db", level=logging.DEBUG)
local_logger.addHandler(RichHandler())

class Logger:

    @staticmethod
    def _log(severity, message):
        if Parent.linked:
            Parent.post("log", timestamp=time.time(),
                               severity =severity.upper(),
                               message  =message)
        else:
            local_logger.log(logging._nameToLevel.get(severity, None), message)

    @staticmethod
    def debug(message):
        return Logger._log("DEBUG", message)

    @staticmethod
    def info(message):
        return Logger._log("INFO", message)

    @staticmethod
    def warning(message):
        return Logger._log("WARNING", message)

    @staticmethod
    def error(message):
        return Logger._log("ERROR", message)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    Logger._log(severity, message)

if __name__ == "__main__":
    logger(prog_name="logger")
