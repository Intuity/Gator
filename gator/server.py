import logging
import socket
import time
from contextlib import closing
from threading import Lock, Thread
from typing import Optional

from flask import cli, Flask, jsonify, request

from .db import Database

class Server:

    def __init__(self, port : Optional[int]=None, db : Database = None):
        self.db = db
        self.app = Flask("gator")
        self.app.route("/")(self.root)
        self.app.post("/log")(self.log)
        self.app.post("/child")(self.child_start)
        self.app.post("/child/complete")(self.child_complete)
        self.app.post("/child/update")(self.child_update)
        self.__port = port
        self.lock = Lock()
        self.lock.acquire()
        Thread(target=self.__run, daemon=True).start()

    @property
    def port(self):
        self.lock.acquire()
        self.lock.release()
        return self.__port

    @property
    def address(self):
        return f"{socket.gethostname()}:{self.port}"

    def __run(self):
        # If no port number provided, choose a random one
        if self.__port is None:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(('', 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__port = s.getsockname()[1]
        # Hide Flask launch messages
        logging.getLogger('werkzeug').disabled = True
        cli.show_server_banner = lambda *_: None
        # Release lock
        self.lock.release()
        # Launch Flask server
        self.app.run(host="0.0.0.0", port=self.__port, debug=False, use_reloader=False)

    def root(self):
        """ Identify Gator and the tool version """
        return jsonify({ "tool": "gator", "version": 0.1 })

    def log(self):
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

    def child_start(self):
        """
        Register a child process with the parent's server.

        Example: { "id": "sub_123", "server": "somehost:1234" }
        """
        data     = request.json
        child_id = data.get("id",     None)
        server   = data.get("server", None)
        print(f"Child {child_id} registered with server {server}")
        return jsonify({ "result": "success" })

    def child_complete(self):
        """
        Mark that a child process has completed.

        Example: { "id": "sub_123", "code": 0 }
        """
        data      = request.json
        child_id  = data.get("id",      None)
        exit_code = data.get("code",    None)
        errors   = data.get("errors",   None)
        warnings = data.get("warnings", None)
        print(f"Child {child_id} completed with {exit_code=}, {warnings=}, {errors=}")
        return jsonify({ "result": "success" })

    def child_update(self):
        """
        Child can report error and warning counts.

        Example: { "id": "sub_123", "errors": 1, "warnings": 3 }
        """
        data     = request.json
        child_id = data.get("id",       None)
        errors   = data.get("errors",   None)
        warnings = data.get("warnings", None)
        print(f"Child {child_id} - {errors=}, {warnings=}")
        return jsonify({ "result": "success" })
