import logging
import socket
import time
from contextlib import closing
from threading import Lock, Thread

from flask import cli, Flask, jsonify, request

class Server:

    def __init__(self, port=None):
        self.app = Flask("gator")
        self.app.route("/")(self.root)
        self.app.post("/log")(self.log)
        self.__port = port
        self.lock = Lock()
        self.lock.acquire()
        Thread(target=self.__run, daemon=True).start()

    @property
    def port(self):
        self.lock.acquire()
        self.lock.release()
        return self.__port

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
        return jsonify({ "tool": "gator", "version": 0.1 })

    def log(self):
        data      = request.json
        timestamp = data.get("timestamp", int(time.time()))
        verbosity = data.get("verbosity", "INFO").strip().upper()
        message   = data.get("message", "N/A").strip()
        if (level := logging._nameToLevel.get(verbosity, None)) is not None:
            logging.log(level, f"[{timestamp}] {message}")
            return jsonify({ "result": "success" })
        else:
            return jsonify({ "result": "bad_verbosity" })
