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
import socket
import time
from contextlib import closing
from threading import Lock, Thread
from typing import Callable, Optional

from flask import cli, Flask, jsonify, request

from .db import Database

class Server:
    """ Wrapper around Flask that exposes a local server with customisable routes """

    def __init__(self,
                 port : Optional[int] = None,
                 db : Database = None) -> None:
        self.db = db
        self.__port = port
        # Create a flask app and register "/" (GET) and "/log" (POST) routes
        self.app = Flask("gator")
        self.register_get("/", self.root)
        self.register_post("/log", self.handle_log)
        # Create a lock which is held until server thread starts
        self.lock = Lock()
        self.lock.acquire()
        self.thread = None

    @property
    def port(self) -> int:
        """ Return the allocated port number """
        # If no port is known, wait for the server to start and be allocated one
        if self.__port is None:
            self.lock.acquire()
            self.lock.release()
        return self.__port

    @property
    def address(self) -> str:
        """ Returns the URI of the server """
        return f"{socket.gethostname()}:{self.port}"

    # ==========================================================================
    # Route Registration
    # ==========================================================================

    def register_get(self, route : str, handler : Callable) -> None:
        """
        Register a GET route with the Flask app

        :param route:   Route to register
        :param handler: Callback method when route is accessed
        """
        self.app.get("/" + route.strip("/"))(handler)

    def register_post(self, route : str, handler : Callable) -> None:
        """
        Register a POST route with the Flask app

        :param route:   Route to register
        :param handler: Callback method when route is accessed
        """
        self.app.post("/" + route.strip("/"))(handler)

    # ==========================================================================
    # Server Thread Management
    # ==========================================================================

    def start(self) -> None:
        """ Start the Flask server on a background thread """
        self.thread = Thread(target=self.__run, daemon=True)
        self.thread.start()

    def __run(self) -> None:
        """ Server process run under thread """
        # If no port number provided, choose a random one
        if self.__port is None:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(('', 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__port = s.getsockname()[1]
        # Hide Flask launch messages
        logging.getLogger('werkzeug').disabled = True
        cli.show_server_banner = lambda *_: None
        # Release lock to unblock port number retrieval
        self.lock.release()
        # Launch Flask server
        self.app.run(host="0.0.0.0", port=self.__port, debug=False, use_reloader=False)

    # ==========================================================================
    # Standard Routes
    # ==========================================================================

    def root(self):
        """ Identify Gator and the tool version """
        return jsonify({ "tool": "gator", "version": 0.1 })

    def handle_log(self):
        """
        Service remote logging request from a child process.

        Example: { "timestamp": 12345678, "severity": "ERROR", "message": "Hello!" }
        """
        data      = request.json
        timestamp = data.get("timestamp", time.time())
        severity  = data.get("severity", "INFO").strip().upper()
        message   = data.get("message", "N/A").strip()
        self.db.push_log(severity, message, int(timestamp))
        return jsonify({"result": "success"})
