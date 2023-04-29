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

import os
from copy import copy, deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from threading import Lock
from typing import Union

from flask import request

from .common.client import Client
from .common.db import Database
from .common.logger import Logger
from .common.server import Server
from .hub.api import HubAPI
from .scheduler import Scheduler
from .specs import Job, JobArray, JobGroup, Spec
from .types import LogEntry

class State(Enum):
    LAUNCHED = auto()
    STARTED  = auto()
    COMPLETE = auto()

@dataclass
class Child:
    spec      : Union[Job, JobArray, JobGroup]
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
                 spec     : Union[JobArray, JobGroup],
                 tracking : Path = Path.cwd() / "tracking",
                 quiet    : bool = False,
                 all_msg  : bool = False) -> None:
        self.spec      = spec
        self.tracking  = tracking
        self.quiet     = quiet
        self.all_msg   = all_msg
        self.db        = None
        self.client    = None
        self.server    = None
        self.children  = {}
        self.scheduler = None

    @classmethod
    async def create(cls, *args, **kwargs) -> None:
        self = cls(*args, **kwargs)
        # Setup database
        self.db = Database(self.tracking / f"{os.getpid()}.sqlite")
        async def _log_cb(entry : LogEntry) -> None:
            await Logger.log(entry.severity.name, entry.message)
        await self.db.start()
        await self.db.register(LogEntry, None if self.quiet else _log_cb)
        # Setup server
        self.server = Server(db=self.db)
        self.server.register("children", self.__list_children)
        self.server.register("spec", self.__child_query)
        self.server.register("register", self.__child_started)
        self.server.register("update", self.__child_updated)
        self.server.register("complete", self.__child_completed)
        server_address = await self.server.start()
        # If an immediate parent is known, register with it
        self.client = await Client.instance().start()
        if self.client.linked:
            await self.client.register(id=self.id, server=server_address)
        # Otherwise, if a hub is known register to it
        elif HubAPI.linked:
            HubAPI.register(self.spec.id, self.server.address)
        # Setup database and server
        await Logger.info(f"Layer '{self.id}' launching sub-jobs")
        await self.__launch()
        # Shutdown the server
        await self.server.stop()
        # Shutdown the database
        await self.db.stop()
        # Shutdown the client
        await self.client.stop()

    @property
    def id(self) -> str:
        return self.spec.id or str(os.getpid())

    async def __list_children(self, **_):
        """ List all of the children of this layer """
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
        return state

    async def __child_query(self, id : str, **_):
        if id in self.children:
            return { "spec": Spec.dump(self.children[id].spec) }
        else:
            await Logger.error(f"Unknown child '{id}'")
            return { "result": "error" }

    async def __child_started(self, id : str, server : str, **_):
        """
        Register a child process with the parent's server.

        Example: { "server": "somehost:1234" }
        """
        if id in self.children:
            child = self.children[id]
            if child.state is not State.LAUNCHED:
                await Logger.error(f"Duplicate start detected for child '{child.id}'")
            child.server  = server
            child.state   = State.STARTED
            child.started = datetime.now()
            child.updated = datetime.now()
            return { "result": "success" }
        else:
            await Logger.error(f"Unknown child '{id}'")
            return { "result": "error" }

    async def __child_updated(self, id : str, errors : int, warnings : int, **_):
        """
        Child can report error and warning counts.

        Example: { "errors": 1, "warnings": 3 }
        """
        if id in self.children:
            child = self.children[id]
            if child.state is not State.STARTED:
                await Logger.error(f"Update received for child '{child.id}' before start")
            child.warnings = int(warnings)
            child.errors   = int(errors)
            child.updated  = datetime.now()
            return { "result": "success" }
        else:
            await Logger.error(f"Unknown child '{id}'")
            return { "result": "error" }

    async def __child_completed(self, id : str, code : int, warnings : int, errors : int, **_):
        """
        Mark that a child process has completed.

        Example: { "code": 1, "warnings": 1, "errors": 2 }
        """
        if id in self.children:
            child = self.children[id]
            if child.state is State.COMPLETE:
                await Logger.error(f"Duplicate completion detected for child '{child.id}'")
            child.state     = State.COMPLETE
            child.warnings  = int(warnings)
            child.errors    = int(errors)
            child.exitcode  = int(code)
            child.updated   = datetime.now()
            child.completed = datetime.now()
            return { "result": "success" }
        else:
            await Logger.error(f"Unknown child '{id}'")
            return { "result": "error" }

    async def __launch(self):
        # Construct each child
        is_jarr = isinstance(self.spec, JobArray)
        for idx_job, job in enumerate(self.spec.jobs):
            # Sanity check
            if not isinstance(job, (Job, JobGroup, JobArray)):
                Logger.error(f"Unexpected job object type {type(job).__name__}")
                continue
            # Propagate environment variables from parent to child
            merged = copy(self.spec.env)
            merged.update(job.env)
            job.env = merged
            # Vary behaviour depending if this a job array or not
            base_job_id = job.id
            for idx_jarr in range(self.spec.repeats if is_jarr else 1):
                if is_jarr:
                    job_cp = deepcopy(job)
                    job_cp.env["GATOR_ARRAY_INDEX"] = idx_jarr
                    job_cp.id = f"T{idx_job}_A{idx_jarr}"
                else:
                    job_cp = job
                    job_cp.id = f"T{idx_job}"
                if base_job_id:
                    job_cp.id += f"_{base_job_id}"
                self.children[job_cp.id] = Child(spec=job_cp, id=job_cp.id)
        # Create a scheduler with all of the specifications
        server_address = await self.server.get_address()
        self.scheduler = Scheduler(tasks=list(self.children.keys()),
                                   parent=server_address,
                                   quiet=not self.all_msg)
        # Launch tasks
        await self.scheduler.launch()
        # Wait until complete
        await self.scheduler.wait_for_all()
