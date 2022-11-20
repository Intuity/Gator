import os
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from typing import Optional

import click
from flask import jsonify, request
from threading import Lock

from .db import Database
from .server import Server
from .scheduler import Scheduler, Task

class State(Enum):
    LAUNCHED = auto()
    STARTED  = auto()
    COMPLETE = auto()

@dataclass
class Child:
    id        : str      = "N/A"
    state     : State    = State.LAUNCHED
    server    : str      = ""
    warnings  : int      = 0
    errors    : int      = 0
    exitcode  : int      = 0
    started   : datetime = datetime.min
    updated   : datetime = datetime.min
    completed : datetime = datetime.min

class Layer:
    """ Layer of the process tree """

    def __init__(self,
                 id       : Optional[str] = None,
                 parent   : Optional[str] = None,
                 port     : Optional[int] = None,
                 tracking : Path = Path.cwd() / "tracking",
                 quiet    : bool = False) -> None:
        self.id       = id or os.getpid()
        self.parent   = parent
        self.tracking = tracking
        # Track children
        self.children  = {}
        self.lock      = Lock()
        self.scheduler = None
        # Setup database and server
        self.db     = Database(self.tracking / f"{self.id}.db", quiet)
        self.server = Server(port, self.db)
        self.server.register_get("/children", self._list_children)
        self.server.register_post("/children/<child_id>", self._child_started)
        self.server.register_post("/children/<child_id>/update", self._child_updated)
        self.server.register_post("/children/<child_id>/complete", self._child_completed)
        self.server.start()
        print(f"Layer server running on address {self.server.address}")
        self.launch()
        self.db.stop()

    def _list_children(self):
        """ List all of the children of this layer """
        self.lock.acquire()
        state = {}
        for child in self.children.values():
            state[child.id] = { "state"    : child.state.name,
                                "server"   : child.server,
                                "warnings" : child.warnings,
                                "errors"   : child.errors,
                                "exitcode" : child.exitcode,
                                "started"  : child.started.isoformat(),
                                "updated"  : child.updated.isoformat(),
                                "completed": child.completed.isoformat() }
        self.lock.release()
        return state

    def _child_started(self, child_id):
        """
        Register a child process with the parent's server.

        Example: { "server": "somehost:1234" }
        """
        data   = request.json
        server = data.get("server", None)
        if child_id in self.children:
            self.lock.acquire()
            child = self.children[child_id]
            if child.state is not State.LAUNCHED:
                print(f"Duplicate start detected for child '{child.id}'")
            child.server  = server
            child.state   = State.STARTED
            child.started = datetime.now()
            child.updated = datetime.now()
            self.lock.release()
            return jsonify({ "result": "success" })
        else:
            print(f"Unknown child '{child_id}'")
            return jsonify({ "result": "error" })

    def _child_updated(self, child_id):
        """
        Child can report error and warning counts.

        Example: { "errors": 1, "warnings": 3 }
        """
        data = request.json
        if child_id in self.children:
            self.lock.acquire()
            child = self.children[child_id]
            if child.state is not State.STARTED:
                print(f"Update received for child '{child.id}' before start")
            child.warnings = data.get("warnings", 0)
            child.errors   = data.get("errors",   0)
            child.updated  = datetime.now()
            self.lock.release()
            return jsonify({ "result": "success" })
        else:
            print(f"Unknown child '{child_id}'")
            return jsonify({ "result": "error" })

    def _child_completed(self, child_id):
        """
        Mark that a child process has completed.

        Example: { "code": 1, "warnings": 1, "errors": 2 }
        """
        data = request.json
        if child_id in self.children:
            self.lock.acquire()
            child = self.children[child_id]
            if child.state is State.COMPLETE:
                print(f"Duplicate completion detected for child '{child.id}'")
            child.state     = State.COMPLETE
            child.warnings  = data.get("warnings", 0)
            child.errors    = data.get("errors",   0)
            child.exitcode  = data.get("code",     0)
            child.updated   = datetime.now()
            child.completed = datetime.now()
            self.lock.release()
            return jsonify({ "result": "success" })
        else:
            print(f"Unknown child '{child_id}'")
            return jsonify({ "result": "error" })

    def launch(self):
        # TODO: Currently using a fixed subprocess set
        self.lock.acquire()
        tasks = []
        for idx in range(5):
            child_id = f"sub_{idx}"
            self.children[child_id] = Child(child_id)
            tasks.append(Task(child_id, ["sleep", str(10 * (idx + 1))]))
        self.lock.release()
        self.scheduler = Scheduler(tasks, self.server.address)
        self.scheduler.wait_for_all()

@click.command()
@click.option("--gator-id",       default=None,  type=str,   help="Job identifier")
@click.option("--gator-parent",   default=None,  type=str,   help="Parent's server")
@click.option("--gator-port",     default=None,  type=int,   help="Port number for server")
@click.option("--gator-tracking", default=None,  type=str,   help="Tracking directory")
@click.option("--gator-quiet",    default=False, count=True, help="Silence local logging")
def layer(gator_id, gator_parent, gator_port, gator_tracking, gator_quiet):
    kwargs = {}
    if gator_port is not None:
        kwargs["port"] = int(gator_port)
    if gator_tracking is not None:
        kwargs["tracking"] = Path(gator_tracking)
    Layer(gator_id, gator_parent, **kwargs, quiet=gator_quiet)

if __name__ == "__main__":
    layer(prog_name="layer", default_map={
        f"gator_{k[6:].lower()}": v
        for k, v in os.environ.items() if k.startswith("GATOR_")
    })
