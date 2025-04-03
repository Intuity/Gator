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

import atexit
import json
import logging
import os
from datetime import datetime
from queue import SimpleQueue
from threading import Event, Thread

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed


class TeardownMarker:
    pass


class GatorHandler(logging.Handler):

    def __init__(self, ws_address: str | None = None):
        super().__init__()
        self._ws_address = ws_address or os.environ.get("GATOR_PARENT", None)
        assert self._ws_address, (
            "Websocket address for parent process is not set and could not be "
            "determined from the environment"
        )
        self._send_q = SimpleQueue[TeardownMarker | tuple[int, str]]()
        self._send_q.put((logging.INFO, "Log forwarding via GatorHandler"))
        self._teardown_evt = Event()
        self._ws_thread = Thread(target=self._manage_ws, daemon=True)
        self._ws_thread.start()
        atexit.register(self._teardown)

    def _manage_ws(self):
        try:
            with connect(f"ws://{self._ws_address}") as ws:
                while True:
                    packet = self._send_q.get()
                    # Check if the process wants us to teardown
                    if isinstance(packet, TeardownMarker):
                        break
                    # Otherwise log the message
                    severity, msg = packet
                    request = {
                        "action": "log",
                        "posted": True,
                        "payload": {
                            "timestamp": datetime.now().timestamp(),
                            "severity": logging._levelToName[severity],
                            "message": msg,
                        }
                    }
                    ws.send(json.dumps(request))
        except ConnectionClosed:
            pass
        # Set the teardown event to signify a clean exit
        self._teardown_evt.set()

    def _teardown(self):
        self._send_q.put(TeardownMarker())
        if not self._teardown_evt.wait(timeout=10):
            print(
                "GatorHandler timed out waiting for the logging thread to tear "
                "down, some log messages may have been missed!"
            )

    def emit(self, record: logging.LogRecord):
        self._send_q.put((record.levelno, record.getMessage()))
