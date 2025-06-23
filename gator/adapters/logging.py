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
from datetime import datetime

from .parent import Parent


class GatorHandler(logging.Handler):
    """
    Custom handler for Python logging to redirect messages via Gator's logging
    API such that severities are correctly recorded.

    :param ws_address: Optional websocket address for the parent tier, otherwise
                       it will be read from the GATOR_PARENT environment variable
    """

    def __init__(self, ws_address: str | None = None):
        super().__init__()
        self._parent = Parent(ws_address)
        self._do_log("INFO", "Log fowarding via GatorHandler", "root")

    def _do_log(self, severity: str, message: str, hierarchy: str):
        self._parent.post(
            "log",
            timestamp=datetime.now().timestamp(),
            hierarchy=hierarchy,
            severity=severity,
            message=message,
        )

    def emit(self, record: logging.LogRecord):
        self._do_log(record.levelname, record.getMessage(), record.name)
