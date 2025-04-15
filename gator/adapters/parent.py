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
import os
import sys
from queue import SimpleQueue
from threading import Event, Thread

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed


class TeardownMarker:
    pass


class Parent:
    """
    Thread based wrapper around the Gator websocket interface

    :param ws_address: Optional websocket address for the parent tier, otherwise
                       it will be read from the GATOR_PARENT environment variable
    """

    def __init__(self, ws_address: str | None = None):
        self._ws_address = ws_address or Parent.get_parent_address()
        assert self._ws_address, (
            "Websocket address for parent process is not set and could not be "
            "determined from the environment"
        )
        self._rx_q = SimpleQueue[dict[str, str]]
        self._tx_q = SimpleQueue[TeardownMarker | dict[str, str]]()
        self._teardown_evt = Event()
        self._ws_thread = Thread(target=self._manage_ws, daemon=True)
        self._ws_thread.start()
        atexit.register(self._teardown)

    @staticmethod
    def get_parent_address() -> str | None:
        return os.environ.get("GATOR_PARENT", None)

    def post(self, action, **payload):
        self._tx_q.put({
            "action": action,
            "posted": True,
            "payload": payload,
        })

    def receive(self) -> dict[str, str]:
        return self._rx_q.get()

    def _manage_ws(self):
        def _receiver(ws, rx_q: SimpleQueue[dict[str, str]]):
            try:
                for packet in ws:
                    rx_q.put(json.loads(packet))
            except ConnectionClosed:
                pass
        rx_thread = None
        try:
            with connect(f"ws://{self._ws_address}") as ws:
                # Setup a receiving thread
                rx_thread = Thread(target=_receiver, daemon=True, args=(ws, self._rx_q))
                rx_thread.start()
                # Transmit until a teardown is inserted
                while True:
                    packet = self._tx_q.get()
                    # Check if the process wants us to teardown
                    if isinstance(packet, TeardownMarker):
                        break
                    # Otherwise log the message
                    ws.send(json.dumps(packet))
        except ConnectionClosed:
            pass
        # Wait for the receiver thread to end
        rx_thread.join()
        # Set the teardown event to signify a clean exit
        self._teardown_evt.set()

    def _teardown(self):
        self._tx_q.put(TeardownMarker())
        if not self._teardown_evt.wait(timeout=10):
            print(
                "Gator timed out waiting for the websocket thread to teardown, "
                "some packets may have been missed!",
                file=sys.stderr,
            )
