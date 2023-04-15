import os
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from typing import Union

from flask import jsonify, request
from threading import Lock

from .db import Database
from .logger import Logger
from .parent import Parent
from .server import Server
from .scheduler import Scheduler
from .specs import Job, JobGroup, Spec

class State(Enum):
    LAUNCHED = auto()
    STARTED  = auto()
    COMPLETE = auto()

@dataclass
class Child:
    spec      : Union[Job, JobGroup]
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
                 spec     : JobGroup,
                 tracking : Path = Path.cwd() / "tracking",
                 quiet    : bool = False) -> None:
        self.spec     = spec
        self.tracking = tracking
        # Setup database and server
        self.db     = Database(self.tracking / f"{self.id}.db", quiet)
        self.server = Server(self.spec.port, self.db)
        self.server.register_get("/children", self._list_children)
        self.server.register_get("/children/<child_id>", self._child_query)
        self.server.register_post("/children/<child_id>", self._child_started)
        self.server.register_post("/children/<child_id>/update", self._child_updated)
        self.server.register_post("/children/<child_id>/complete", self._child_completed)
        self.server.start()
        Parent.register(self.spec.id, self.server.address)
        # Track children
        self.children  = {}
        self.lock      = Lock()
        self.scheduler = None
        # Setup database and server
        Logger.info(f"Layer '{self.id}' launching sub-jobs")
        self.launch()
        self.db.stop()

    @property
    def id(self) -> str:
        return self.spec.id or str(os.getpid())

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

    def _child_query(self, child_id : str):
        if child_id in self.children:
            return jsonify({
                "result": "success",
                "spec"  : Spec.dump(self.children[child_id].spec)
            })
        else:
            Logger.error(f"Unknown child '{child_id}'")
            return jsonify({ "result": "error" })

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
                Logger.error(f"Duplicate start detected for child '{child.id}'")
            child.server  = server
            child.state   = State.STARTED
            child.started = datetime.now()
            child.updated = datetime.now()
            self.lock.release()
            return jsonify({ "result": "success" })
        else:
            Logger.error(f"Unknown child '{child_id}'")
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
        self.lock.acquire()
        for idx, job in enumerate(self.spec.jobs):
            if not isinstance(job, (Job, JobGroup)):
                print(f"Unexpected job object type {type(job).__name__}")
                continue
            job.id = f"T{idx}" + (f"_{job.id}" if job.id else "")
            self.children[job.id] = Child(spec=job, id=job.id)
        self.lock.release()
        self.scheduler = Scheduler(tasks=list(self.children.keys()),
                                   parent=self.server.address)
        self.scheduler.wait_for_all()
