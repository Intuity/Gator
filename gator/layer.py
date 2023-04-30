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

import asyncio
import os
from copy import copy, deepcopy
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from typing import List, Union

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
    spec       : Union[Job, JobArray, JobGroup]
    id         : str           = "N/A"
    state      : State         = State.LAUNCHED
    server     : str           = ""
    warnings   : int           = 0
    errors     : int           = 0
    exitcode   : int           = 0
    started    : datetime      = datetime.min
    updated    : datetime      = datetime.min
    completed  : datetime      = datetime.min
    e_complete : asyncio.Event = field(default_factory=asyncio.Event)

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
        self.scheduler = None
        self.lock      = asyncio.Lock()
        # Tracking for jobs in different phases
        self.launched  = {}
        self.pending   = {}
        self.complete  = {}
        # Tasks for pending jobs
        self.job_tasks = []

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
        # Create a scheduler
        self.scheduler = Scheduler(parent=server_address, quiet=not self.all_msg)
        # Launch jobs
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
        async with self.lock:
            for key, store in (("launched", self.launched),
                            ("pending",  self.pending ),
                            ("complete", self.complete)):
                state[key] = {}
                for child in store.values():
                    state[key][child.id] = { "state"    : child.state.name,
                                            "server"   : child.server,
                                            "warnings" : child.warnings,
                                            "errors"   : child.errors,
                                            "exitcode" : child.exitcode,
                                            "started"  : child.started.isoformat(),
                                            "updated"  : child.updated.isoformat(),
                                            "completed": child.completed.isoformat() }
        return state

    async def __child_query(self, id : str, **_):
        """ Return the specification for a launched process """
        async with self.lock:
            if id in self.launched:
                return { "spec": Spec.dump(self.launched[id].spec) }
            else:
                await Logger.error(f"Unknown child '{id}'")
                return { "result": "error" }

    async def __child_started(self, id : str, server : str, **_):
        """
        Register a child process with the parent's server.

        Example: { "server": "somehost:1234" }
        """
        async with self.lock:
            if id in self.launched:
                child = self.launched[id]
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
        async with self.lock:
            if id in self.launched:
                child = self.launched[id]
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
        async with self.lock:
            if id in self.launched:
                child = self.launched[id]
                # Apply updates
                child.state     = State.COMPLETE
                child.warnings  = int(warnings)
                child.errors    = int(errors)
                child.exitcode  = int(code)
                child.updated   = datetime.now()
                child.completed = datetime.now()
                # Move to the completed store
                self.complete[child.id] = child
                del self.launched[child.id]
                # Trigger complete event
                await Logger.info(f"Setting complete event for {id}")
                child.e_complete.set()
                return { "result": "success" }
            else:
                await Logger.error(f"Unknown child '{id}'")
                return { "result": "error" }

    async def __postpone(self, id : str, wait_for : List[Child], to_launch : List[Child]) -> None:
        await asyncio.gather(*(x.e_complete.wait() for x in wait_for))
        await Logger.info(f"Dependencies of {id} complete, now launching")
        # Accumulate errors and absolute exit codes for all dependencies
        by_id = defaultdict(lambda: 0)
        for child in wait_for:
            by_id[child.spec.id] += child.errors + abs(child.exitcode)
        # Check if pass/fail criteria is met
        all_ok = True
        for spec in set(x.spec for x in to_launch):
            for result, dep_ids in ((True, spec.on_pass), (False, spec.on_fail)):
                for id in dep_ids:
                    if result and by_id[id] != 0:
                        await Logger.warning(f"Dependency '{id}' failed so "
                                            f"{type(spec).__name__} '{spec.id}' "
                                            f"will be pruned")
                        all_ok = False
                        break
                    elif not result and by_id[id] == 0:
                        await Logger.warning(f"Dependency '{id}' passed so "
                                            f"{type(spec).__name__} '{spec.id}' "
                                            f"will be pruned")
                        all_ok = False
                        break
                    if not all_ok:
                        break
        if not all_ok:
            async with self.lock:
                for child in to_launch:
                    del self.pending[child.id]
            return
        # Launch
        async with self.lock:
            for child in to_launch:
                self.launched[child.id] = child
                del self.pending[child.id]
            await self.scheduler.launch([x.id for x in to_launch])

    async def __launch(self):
        # Construct each child
        is_jarr = isinstance(self.spec, JobArray)
        grouped = defaultdict(list)
        for idx_job, job in enumerate(self.spec.jobs):
            # Sanity check
            if not isinstance(job, (Job, JobGroup, JobArray)):
                Logger.error(f"Unexpected job object type {type(job).__name__}")
                continue
            # Propagate environment variables from parent to child
            merged = copy(self.spec.env)
            merged.update(job.env)
            job.env = merged
            # Propagate working directory from parent to child
            job.cwd = job.cwd or self.spec.cwd
            # Vary behaviour depending if this a job array or not
            for idx_jarr in range(self.spec.repeats if is_jarr else 1):
                if is_jarr:
                    job_cp = deepcopy(job)
                    job_cp.env["GATOR_ARRAY_INDEX"] = idx_jarr
                    child_id = f"T{idx_job}_A{idx_jarr}"
                else:
                    job_cp = job
                    child_id = f"T{idx_job}"
                if job.id:
                    child_id += f"_{job.id}"
                grouped[job.id].append(Child(spec=job_cp, id=child_id))
        # Launch or create dependencies
        async with self.lock:
            for id, children in grouped.items():
                spec = children[0].spec
                # If dependencies are required, form them
                if spec.on_pass or spec.on_fail or spec.on_done:
                    resolved = []
                    bad_deps = False
                    for dep_id in (spec.on_pass + spec.on_fail + spec.on_done):
                        if dep_id not in grouped or len(grouped[dep_id]) == 0:
                            await Logger.error(f"Could not resolve dependency '{dep_id}' "
                                               f"of job '{id}', so job will never be "
                                               f"launched")
                            bad_deps = True
                            break
                        resolved += grouped[dep_id]
                    if bad_deps:
                        continue
                    # Setup a task to wait until dependencies complete
                    self.job_tasks.append(asyncio.create_task(self.__postpone(id, resolved, children)))
                    # Add to the pending store
                    for child in children:
                        self.pending[child.id] = child
                # Otherwise launch the child immediately
                else:
                    for child in children:
                        self.launched[child.id] = child
            # Schedule all 'launched' jobs
            await self.scheduler.launch(list(self.launched.keys()))
        # Wait for all dependency tasks to complete
        await Logger.info(f"Waiting for {len(self.job_tasks)} dependency tasks to complete")
        await asyncio.gather(*self.job_tasks)
        # Wait until all launched jobs complete
        async with self.lock:
            all_launched = list(self.launched.values())
        await Logger.info(f"Dependency tasks complete, waiting for "
                          f"{len(all_launched)} launched jobs to complete")
        await asyncio.gather(*(x.e_complete.wait() for x in all_launched))
        # Wait until complete
        await Logger.info("Waiting for scheduler to finish")
        await self.scheduler.wait_for_all()
        # Mark this layer as complete
        # TODO: Summarise all warnings and errors from child processes
        await self.client.complete(id=self.id, code=0, warnings=0, errors=0)
