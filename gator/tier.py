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
from copy import copy, deepcopy
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Type

from .common.child import Child, ChildState
from .common.layer import BaseLayer
from .common.logger import Logger
from .common.types import Metric, Result
from .common.ws_wrapper import WebsocketWrapper
from .scheduler import LocalScheduler
from .specs import Job, JobArray, JobGroup, Spec


class Tier(BaseLayer):
    """ Tier of the job tree """

    def __init__(self, *args, scheduler : Type = LocalScheduler, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sched_cls = scheduler
        self.scheduler = None
        self.lock      = asyncio.Lock()
        # Tracking for jobs in different phases
        self.jobs_launched  = {}
        self.jobs_pending   = {}
        self.jobs_completed = {}
        # Tasks for pending jobs
        self.job_tasks = []

    async def launch(self, *args, **kwargs) -> None:
        await self.setup(*args, **kwargs)
        # Register server handlers for the upwards calls
        self.server.add_route("children", self.__list_children)
        self.server.add_route("spec", self.__child_query)
        self.server.add_route("register", self.__child_started)
        self.server.add_route("update", self.__child_updated)
        self.server.add_route("complete", self.__child_completed)
        # Register client handlers for downwards calls
        self.client.add_route("get_tree", self.get_tree)
        # Create a scheduler
        self.scheduler = self.sched_cls(parent=await self.server.get_address(),
                                        quiet =not self.all_msg)
        # Launch jobs
        await self.logger.info(f"Layer '{self.id}' launching sub-jobs")
        await self.__launch()
        # Report
        summary = await self.summarise()
        await self.logger.info(f"Complete - W: {summary['warnings']}, E: {summary['errors']}, "
                               f"T: {summary['sub_total']}, A: {summary['sub_active']}, "
                               f"P: {summary['sub_passed']}, F: {summary['sub_failed']}")
        # Teardown
        await self.teardown(*args, **kwargs)

    async def stop(self, **kwargs) -> None:
        await super().stop(**kwargs)
        await self.logger.warning("Stopping all jobs")
        async with self.lock:
            for child in self.jobs_launched.values():
                await child.ws.stop(posted=True)

    async def get_tree(self, **_) -> Dict[str, Any]:
        tree = {}
        async with self.lock:
            all_launched = list(self.jobs_launched.values())
        for child in all_launched:
            if isinstance(child.spec, Job) or child.ws is None:
                tree[child.id] = child.state.name
            else:
                tree[child.id] = await child.ws.get_tree()
        return tree

    async def __list_children(self, **_):
        """ List all of the children of this layer """
        state = {}
        async with self.lock:
            for key, store in (("launched",  self.jobs_launched ),
                               ("pending",   self.jobs_pending  ),
                               ("completed", self.jobs_completed)):
                state[key] = {}
                for child in store.values():
                    state[key][child.id] = { "state"    : child.state.name,
                                             "result"   : child.result.name,
                                             "server"   : child.server,
                                             "metrics"  : { x.name: x.value for x in child.metrics.values() },
                                             "exitcode" : child.exitcode,
                                             "started"  : int(child.started.timestamp()),
                                             "updated"  : int(child.updated.timestamp()),
                                             "completed": int(child.completed.timestamp()) }
        return state

    async def __child_query(self, id : str, **_):
        """ Return the specification for a launched process """
        async with self.lock:
            if id in self.jobs_launched:
                return { "spec": Spec.dump(self.jobs_launched[id].spec) }
            else:
                await self.logger.error(f"Unknown child of {self.id} query '{id}'")
                raise Exception(f"Bad child ID {id}")

    async def __child_started(self,
                              ws     : WebsocketWrapper,
                              id     : str,
                              server : str,
                              **_):
        """
        Register a child process with the parent's server.

        Example: { "server": "somehost:1234" }
        """
        async with self.lock:
            if id in self.jobs_launched:
                child = self.jobs_launched[id]
                if child.state is not ChildState.LAUNCHED:
                    await self.logger.error(f"Duplicate start detected for child '{child.id}'")
                await self.logger.debug(f"Child {id} of {self.id} has started")
                child.server  = server
                child.state   = ChildState.STARTED
                child.started = datetime.now()
                child.updated = datetime.now()
                child.ws      = ws
            else:
                await self.logger.error(f"Unknown child of {self.id} start '{id}'")
                raise Exception(f"Bad child ID {id}")

    async def __child_updated(self,
                              id         : str,
                              metrics    : Dict[str, List[int]],
                              sub_total  : int = 0,
                              sub_active : int = 0,
                              sub_passed : int = 0,
                              sub_failed : int = 0,
                              **_):
        """
        Child can report the number of jobs it knows about, how many are running,
        and how many have passed or failed. The child may also report arbitrary
        metrics, which are aggregated hierarchically.

        Example: { "id"        : "regression",
                   "sub_total" : 10,
                   "sub_active": 4,
                   "sub_passed": 1,
                   "sub_failed": 2,
                   "metrics"  : {
                     "msg_debug"   : 3,
                     "msg_info"    : 5,
                     "msg_warning" : 2,
                     "msg_error"   : 0,
                     "msg_critical": 0
                   } }
        """
        async with self.lock:
            if id in self.jobs_launched:
                child = self.jobs_launched[id]
                if child.state is not ChildState.STARTED:
                    await self.logger.error(f"Update received for child '{child.id}' before start")
                await self.logger.debug(f"Received update from child {id} of {self.id}")
                child.updated = datetime.now()
                for m_key, m_val in metrics.items():
                    if m_key not in child.metrics:
                        child.metrics[m_key] = Metric(name=m_key)
                    child.metrics[m_key].value = m_val
                child.sub_total  = sub_total
                child.sub_active = sub_active
                child.sub_passed = sub_passed
                child.sub_failed = sub_failed
            elif id in self.jobs_completed:
                await self.logger.error(f"Child {id} of {self.id} sent update after completion")
                raise Exception("Child sent update after completion")
            else:
                await self.logger.error(f"Unknown child {id} of {self.id} update")
                raise Exception(f"Bad child ID {id}")

    async def __child_completed(self,
                                id         : str,
                                result     : str,
                                code       : int,
                                metrics    : Dict[str, List[int]],
                                sub_total  : int = 0,
                                sub_passed : int = 0,
                                sub_failed : int = 0,
                                **_):
        """
        Mark that a child process has completed.

        Example: { "id"        : "regression",
                   "result"    : "SUCCESS",
                   "code"      : 0,
                   "sub_total" : 10,
                   "sub_passed": 1,
                   "sub_failed": 2,
                   "metrics"  : {
                     "msg_debug"   : 3,
                     "msg_info"    : 5,
                     "msg_warning" : 2,
                     "msg_error"   : 0,
                     "msg_critical": 0
                   } }
        """
        async with self.lock:
            if id in self.jobs_launched:
                await self.logger.debug(f"Child {id} of {self.id} has completed")
                child = self.jobs_launched[id]
                # Apply updates
                child.updated   = datetime.now()
                child.completed = datetime.now()
                child.state     = ChildState.COMPLETE
                child.result    = getattr(Result, result.strip().upper())
                for m_key, m_val in metrics.items():
                    if m_key not in child.metrics:
                        child.metrics[m_key] = Metric(name=m_key)
                    child.metrics[m_key].value = m_val
                child.exitcode   = int(code)
                child.sub_total  = sub_total
                child.sub_active = 0
                child.sub_passed = sub_passed
                child.sub_failed = sub_failed
                # Move to the completed store
                self.jobs_completed[child.id] = child
                del self.jobs_launched[child.id]
                # Trigger complete event
                child.e_complete.set()
            elif id in self.jobs_completed:
                await self.logger.error(f"Child {id} of {self.id} sent repeated completion")
                raise Exception("Child sent a second completion message")
            else:
                await self.logger.error(f"Unknown child of {self.id} completion '{id}'")
                raise Exception(f"Bad child ID {id}")

    async def __postpone(self, id : str, wait_for : List[Child], to_launch : List[Child]) -> None:
        await asyncio.gather(*(x.e_complete.wait() for x in wait_for))
        # If terminated, then don't launch further jobs
        if self.terminated:
            await self.logger.info(f"Skipping {id} as tier has been terminated")
            for child in to_launch:
                child.e_complete.set()
            return
        # Accumulate results for all dependencies
        await self.logger.info(f"Dependencies of {id} complete, testing for launch")
        by_id = { x.spec.id: x.result for x in wait_for }
        # Check if pass/fail criteria is met
        all_ok = True
        for spec in set(x.spec for x in to_launch):
            for result, dep_ids in ((True, spec.on_pass), (False, spec.on_fail)):
                for id in dep_ids:
                    if result and by_id[id] != Result.SUCCESS:
                        await self.logger.warning(f"Dependency '{id}' failed so "
                                                  f"{type(spec).__name__} '{spec.id}' "
                                                  f"will be pruned")
                        all_ok = False
                        break
                    elif not result and by_id[id] == Result.SUCCESS:
                        await self.logger.warning(f"Dependency '{id}' passed so "
                                                  f"{type(spec).__name__} '{spec.id}' "
                                                  f"will be pruned")
                        all_ok = False
                        break
                    if not all_ok:
                        break
        if not all_ok:
            async with self.lock:
                for child in to_launch:
                    del self.jobs_pending[child.id]
            return
        # Launch
        async with self.lock:
            for child in to_launch:
                child.state = ChildState.LAUNCHED
                self.jobs_launched[child.id] = child
                del self.jobs_pending[child.id]
            await self.scheduler.launch(to_launch)

    async def summarise(self) -> Dict[str, int]:
        data = defaultdict(lambda: 0)
        data.update(await super().summarise())
        async with self.lock:
            for child in (list(self.jobs_launched.values()) + list(self.jobs_completed.values())):
                for metric in child.metrics.values():
                    data["metrics"][metric.name] += metric.value
                data["sub_total"]  += child.sub_total
                data["sub_active"] += child.sub_active
                data["sub_passed"] += child.sub_passed
                data["sub_failed"] += child.sub_failed
        # While jobs are still starting up, estimate the total number expected
        data["sub_total"] = max(data["sub_total"], self.spec.expected_jobs)
        return data

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
            base_job_id  = job.id if job.id else f"T{idx_job}"
            base_trk_dir = self.tracking / base_job_id
            for idx_jarr in range(self.spec.repeats if is_jarr else 1):
                child_id  = base_job_id
                child_dir = base_trk_dir
                if is_jarr:
                    job_cp = deepcopy(job)
                    job_cp.env["GATOR_ARRAY_INDEX"] = idx_jarr
                    child_id  += f"_{idx_jarr}"
                    child_dir  = base_trk_dir / str(idx_jarr)
                else:
                    job_cp = job
                child_dir.mkdir(parents=True, exist_ok=True)
                grouped[job.id].append(Child(spec    =job_cp,
                                             id      =child_id,
                                             tracking=child_dir))
        # Launch or create dependencies
        async with self.lock:
            bad_deps = False
            for id, children in grouped.items():
                spec = children[0].spec
                # If dependencies are required, form them
                if spec.on_pass or spec.on_fail or spec.on_done:
                    resolved = []
                    for dep_id in (spec.on_pass + spec.on_fail + spec.on_done):
                        if dep_id not in grouped or len(grouped[dep_id]) == 0:
                            await self.logger.error(f"Could not resolve dependency '{dep_id}' "
                                                    f"of job '{id}', so job can never be "
                                                    f"launched")
                            bad_deps = True
                            break
                        resolved += grouped[dep_id]
                    # Check if a task depends on itself
                    if len({x.id for x in children}.intersection({x.id for x in resolved})) > 0:
                        await self.logger.error(f"Cannot schedule job '{id}' as it depends on itself")
                        bad_deps = True
                    # If bad dependencies detected, break out
                    if bad_deps:
                        continue
                    # Setup a task to wait until dependencies complete
                    self.job_tasks.append(asyncio.create_task(self.__postpone(id, resolved, children)))
                    # Add to the pending store
                    for child in children:
                        self.jobs_pending[child.id] = child
                # Otherwise launch the child immediately
                else:
                    for child in children:
                        child.state = ChildState.LAUNCHED
                        self.jobs_launched[child.id] = child
            # If bad dependencies detected, stop
            if bad_deps:
                await self.logger.error("Terminating due to bad dependencies")
                self.complete   = True
                self.terminated = True
                return
            # Schedule all 'launched' jobs
            await self.scheduler.launch(list(self.jobs_launched.values()))
        # Wait for all dependency tasks to complete
        await self.logger.info(f"Waiting for {len(self.job_tasks)} dependency tasks to complete")
        await asyncio.gather(*self.job_tasks)
        # Wait until all launched jobs complete
        async with self.lock:
            all_launched = list(self.jobs_launched.values())
        await self.logger.info(f"Dependency tasks complete, waiting for "
                          f"{len(all_launched)} launched jobs to complete")
        await asyncio.gather(*(x.e_complete.wait() for x in all_launched))
        # Wait until complete
        await self.logger.info("Waiting for scheduler to finish")
        await self.scheduler.wait_for_all()
        # Mark complete
        self.complete = True
