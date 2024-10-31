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
from collections import defaultdict
from copy import copy, deepcopy
from datetime import datetime
from typing import Dict, List, Optional, Type

from .common.child import Child
from .common.db_client import child_client
from .common.layer import (
    BaseLayer,
    GetTreeResponse,
    SpecResponse,
)
from .common.logger import Logger
from .common.summary import Summary, contextualise_summary, merge_summaries
from .common.types import (
    ApiChildren,
    ApiJob,
    Attribute,
    ChildEntry,
    JobResult,
    JobState,
)
from .common.ws_wrapper import WebsocketWrapper
from .scheduler import LocalScheduler, SchedulerError
from .specs import Job, JobArray, JobGroup, Spec


class Tier(BaseLayer):
    """Tier of the job tree"""

    def __init__(
        self,
        *args,
        scheduler: Type = LocalScheduler,
        sched_opts: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.sched_cls = scheduler
        self.sched_opts = sched_opts or {}
        self.scheduler = None
        self.lock = asyncio.Lock()
        # Tracking for jobs in different phases
        self.jobs_pending: Dict[str, Child] = {}
        self.jobs_launched: Dict[str, Child] = {}
        self.jobs_completed: Dict[str, Child] = {}
        # Tasks for pending jobs
        self.job_tasks: list[asyncio.Task] = []

    @property
    def all_children(self) -> Dict[str, Child]:
        return {
            **self.jobs_pending,
            **self.jobs_launched,
            **self.jobs_completed,
        }

    async def launch(self, *args, **kwargs) -> Summary:
        await self.setup(*args, **kwargs)
        # Register server handlers for the upwards calls
        self.server.add_route("children", self.__list_children)
        self.server.add_route("spec", self.__child_query)
        self.server.add_route("register", self.__child_started)
        self.server.add_route("update", self.__child_updated)
        self.server.add_route("complete", self.__child_completed)
        await self.db.register(ChildEntry)
        # Register client handlers for downwards calls
        self.client.add_route("get_tree", self.get_tree)
        # Create a scheduler
        try:
            self.scheduler = self.sched_cls(
                parent=await self.server.get_address(),
                quiet=not self.all_msg,
                logger=self.logger,
                options=self.sched_opts,
                limits=self.limits,
            )
        except SchedulerError as e:
            await self.logger.critical(str(e))
            await self.teardown()
            return

        # Record start time
        self.started = self.updated = datetime.now().timestamp()
        await self.db.push_attribute(Attribute(name="started", value=str(self.started)))
        # Launch jobs
        await self.logger.info(f"Layer '{self.ident}' launching sub-jobs")
        await self.__launch()
        # Record stop time
        self.stopped = self.updated = datetime.now().timestamp()
        await self.db.push_attribute(Attribute(name="stopped", value=str(self.stopped)))

        # Report
        summary = await self.summarise()
        metrics = summary["metrics"]
        await self.logger.info(
            f"Complete - "
            f"W: {metrics.get('msg_warning', 0)}, "
            f"E: {metrics.get('msg_error', 0)}, "
            f"C: {metrics.get('msg_critical', 0)}, "
            f"T: {metrics.get('sub_total', 0)}, A: {metrics.get('sub_active', 0)}, "
            f"P: {metrics.get('sub_passed', 0)}, F: {metrics.get('sub_failed', 0)}"
        )
        # Teardown
        await self.teardown(*args, **kwargs)
        return summary

    async def stop(self, **kwargs) -> None:
        await super().stop(**kwargs)
        await self.logger.warning("Stopping all jobs")
        async with self.lock:
            for child in self.jobs_launched.values():
                if child.ws:
                    await child.ws.stop(posted=True)

    async def get_tree(self, **_) -> GetTreeResponse:
        tree = {}
        async with self.lock:
            all_launched = list(self.jobs_launched.values())
        for child in all_launched:
            if isinstance(child.spec, Job) or child.ws is None:
                tree[child.ident] = child.state.name
            elif child.ws:
                tree[child.ident] = await child.ws.get_tree()
        return tree

    async def __list_children(self, **_) -> ApiChildren:
        """List all of the children of this layer"""
        children: List[ApiJob] = []
        for child in self.all_children.values():
            children.append(
                ApiJob(
                    uidx=child.entry.db_uid,
                    root=self.root,
                    path=[*self.path, self.ident],
                    ident=child.ident,
                    status=child.state,
                    metrics=self.metrics.dump(child.ident),
                    server_url=child.entry.server_url,
                    db_file=(child.tracking / "db.sqlite").as_posix(),
                    started=child.entry.started,
                    updated=child.entry.updated,
                    stopped=child.entry.stopped,
                    result=child.entry.result,
                    owner=None,
                    children=[],
                    expected_children=child.entry.expected_children,
                )
            )
        return ApiChildren(children=children, status=JobState.STARTED)

    async def resolve(
        self, root_path: List[str], nest_path: Optional[List[str]] = None, depth: int = 0, **_
    ) -> ApiJob:
        # Tunnel down to root
        if root_path:
            child = self.all_children[root_path[0]]
            async with child_client(child) as cli:
                if not cli:
                    raise RuntimeError(
                        f"Can't resolve `{child.ident}` as the job hasn't started yet!"
                    )
                return await cli.resolve(root_path=root_path[1:], nest_path=nest_path, depth=depth)

        # Resolve self
        data = await super().resolve(root_path=root_path, nest_path=nest_path, depth=depth)

        # Resolve nested path
        children: List[ApiJob] = []
        if nest_path:
            child = self.all_children[nest_path[0]]
            async with child_client(child) as cli:
                children.append(
                    await cli.resolve(root_path=[], nest_path=nest_path[1:], depth=depth)
                )
        elif depth > 1:
            for child in self.all_children.values():
                async with child_client(child) as cli:
                    if not cli:
                        continue
                    children.append(
                        await cli.resolve(root_path=[], nest_path=nest_path[1:], depth=depth)
                    )
        elif depth == 1:
            for child in self.all_children.values():
                children.append(
                    ApiJob(
                        uidx=child.entry.db_uid,
                        root=self.root,
                        path=[*self.path, self.ident],
                        ident=child.ident,
                        status=child.state,
                        metrics=self.metrics.dump(child.ident),
                        server_url=child.entry.server_url,
                        db_file=(child.tracking / "db.sqlite").as_posix(),
                        started=child.entry.started,
                        updated=child.entry.updated,
                        stopped=child.entry.stopped,
                        result=child.entry.result,
                        owner=None,
                        children=[],
                        expected_children=child.entry.expected_children,
                    )
                )

        data["children"] = children
        data["expected_children"] = len(self.all_children)
        return data

    async def __child_query(self, ident: str, **_) -> SpecResponse:
        """Return the specification for a launched process"""
        async with self.lock:
            if ident in self.jobs_launched:
                return {"spec": Spec.dump(self.jobs_launched[ident].spec)}
            else:
                await self.logger.error(f"Unknown child of {self.ident} query '{ident}'")
                raise Exception(f"Bad child ident {ident}")

    async def __child_started(self, ws: WebsocketWrapper, ident: str, server: str, **_):
        """
        Register a child process with the parent's server.

        Example: { "server": "somehost:1234" }
        """
        async with self.lock:
            if ident in self.jobs_launched:
                child = self.jobs_launched[ident]
                if child.state is not JobState.LAUNCHED:
                    await self.logger.error(f"Duplicate start detected for child '{child.ident}'")
                await self.logger.debug(f"Child {ident} of {self.ident} has started")
                child.state = JobState.STARTED
                child.entry.started = child.entry.updated = datetime.now().timestamp()
                child.entry.server_url = server
                await self.db.update_childentry(child.entry)
                child.ws = ws
                return {
                    "path": [*self.path, self.ident],
                    "root": self.root,
                    "uidx": child.entry.db_uid or 0,
                }
            else:
                await self.logger.error(f"Unknown child of {self.ident} start '{ident}'")
                raise Exception(f"Bad child ident {ident}")

    async def __child_updated(
        self,
        ident: str,
        result: JobResult,
        summary: Summary,
        **_,
    ):
        """
        Child can report the number of jobs it knows about, how many are running,
        and how many have passed or failed. The child may also report arbitrary
        metrics, which are aggregated hierarchically.

        Example: {
            "ident"        : "regression",
            "summary"      : {
                "failed_ids": [
                    ["child_a", "grandchild_a"],
                    ["child_a", "grandchild_c"],
                    ["child_b", "grandchild_f"]
                ],
                "metrics"   : {
                    "sub_total" : 10,
                    "sub_active": 4,
                    "sub_passed": 1,
                    "sub_failed": 2,
                    "msg_debug"   : 3,
                    "msg_info"    : 5,
                    "msg_warning" : 2,
                    "msg_error"   : 0,
                    "msg_critical": 0
                }
            }
        }
        """
        async with self.lock:
            if ident in self.jobs_launched:
                child: Child = self.jobs_launched[ident]
                if child.state is not JobState.STARTED:
                    await self.logger.error(
                        f"Update received for child '{child.ident}' before start"
                    )
                await self.logger.debug(f"Received update from child {ident} of {self.ident}")
                child.entry.updated = datetime.now().timestamp()
                child.entry.result = JobResult(result)
                if child.entry.result == JobResult.FAILURE:
                    self.result = JobResult.FAILURE
                child.summary = contextualise_summary(self.spec.ident, summary)
                await self.db.update_childentry(child.entry)
            elif ident in self.jobs_completed:
                await self.logger.error(
                    f"Child {ident} of {self.ident} sent update after completion"
                )
                raise Exception("Child sent update after completion")
            else:
                await self.logger.error(f"Unknown child {ident} of {self.ident} update")
                raise Exception(f"Bad child ident {ident}")

    async def __child_completed(
        self,
        ident: str,
        result: JobResult,
        code: int,
        summary: Summary,
        **_,
    ):
        """
        Mark that a child process has completed.

        Example: {
            "ident"     : "regression",
            "result"    : "SUCCESS",
            "code"      : 0,
            "summary"   : {
                "failed_ids": [
                    ["child_a", "grandchild_a"],
                    ["child_a", "grandchild_c"],
                    ["child_b", "grandchild_f"]
                ],
                "metrics"   : {
                    "sub_total" : 10,
                    "sub_passed": 1,
                    "sub_failed": 2,
                    "msg_debug"   : 3,
                    "msg_info"    : 5,
                    "msg_warning" : 2,
                    "msg_error"   : 0,
                    "msg_critical": 0
                }
            }
        }
        """
        async with self.lock:
            if ident in self.jobs_launched:
                await self.logger.debug(
                    f"Child {ident} of {self.ident} has completed with {result}"
                )
                child = self.jobs_launched[ident]
                # Apply updates
                child.state = JobState.COMPLETE
                child.summary = contextualise_summary(self.spec.ident, summary)
                child.entry.db_file = (child.tracking / "db.sqlite").as_posix()
                child.entry.stopped = child.entry.updated = datetime.now().timestamp()
                child.entry.result = JobResult(result)
                if child.entry.result == JobResult.FAILURE:
                    self.result = JobResult.FAILURE
                await self.db.update_childentry(child.entry)

                if child.summary["metrics"].get("sub_active", 0):
                    await self.logger.error(
                        f"Child {ident} of {self.ident} reported active jobs on completion"
                    )
                    raise Exception("Child reported active jobs on completion")
                child.exitcode = int(code)
                # Move to the completed store
                self.jobs_completed[child.ident] = child
                del self.jobs_launched[child.ident]
                # Trigger complete event
                child.e_complete.set()
            elif ident in self.jobs_completed:
                await self.logger.error(f"Child {ident} of {self.ident} sent repeated completion")
                raise Exception("Child sent a second completion message")
            else:
                await self.logger.error(f"Unknown child of {self.ident} completion '{ident}'")
                raise Exception(f"Bad child ident {ident}")

    async def __postpone(self, ident: str, wait_for: List[Child], to_launch: List[Child]) -> None:
        await asyncio.gather(*(x.e_complete.wait() for x in wait_for))
        # If terminated, then don't launch further jobs
        if self.terminated:
            await self.logger.info(f"Skipping {ident} as tier has been terminated")
            for child in to_launch:
                child.e_complete.set()
            return
        # Accumulate results for all dependencies
        await self.logger.info(f"Dependencies of {ident} complete, testing for launch")
        by_id = {x.spec.ident: x.entry.result for x in wait_for}
        # Check if pass/fail criteria is met
        all_ok = True
        for spec in (x.spec for x in to_launch):
            for result, dep_ids in (
                (True, spec.on_pass),
                (False, spec.on_fail),
            ):
                for ident in dep_ids:
                    if result and by_id[ident] != JobResult.SUCCESS:
                        await self.logger.warning(
                            f"Dependency '{ident}' failed so "
                            f"{type(spec).__name__} '{spec.ident}' "
                            f"will be pruned"
                        )
                        all_ok = False
                        break
                    elif not result and by_id[ident] == JobResult.SUCCESS:
                        await self.logger.warning(
                            f"Dependency '{ident}' passed so "
                            f"{type(spec).__name__} '{spec.ident}' "
                            f"will be pruned"
                        )
                        all_ok = False
                        break
                    if not all_ok:
                        break
        if not all_ok:
            async with self.lock:
                for child in to_launch:
                    child.state = JobState.COMPLETE
                    child.entry.result = JobResult.ABORTED
                    self.jobs_completed[child.ident] = child

                    del self.jobs_pending[child.ident]
                    await self.db.update_childentry(child.entry)
                    child.e_complete.set()
            return
        # Launch
        async with self.lock:
            for child in to_launch:
                child.state = JobState.LAUNCHED
                self.jobs_launched[child.ident] = child
                del self.jobs_pending[child.ident]
            await self.scheduler.launch(to_launch)

    async def summarise(self) -> Summary:
        data = await super().summarise()
        async with self.lock:
            for child in list(self.jobs_launched.values()) + list(self.jobs_completed.values()):
                for name, value in child.summary["metrics"].items():
                    self.metrics.set(child.ident, name, value)
                data = merge_summaries(data, child.summary)

        # While jobs are still starting up, estimate the total number expected
        data["metrics"]["sub_total"] = max(
            data["metrics"].get("sub_total", 0),
            self.spec.expected_jobs + 1,  # (+1 for self)
        )
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
            base_job_id = job.ident if job.ident else f"T{idx_job}"
            base_trk_dir = self.tracking / base_job_id
            for idx_jarr in range(self.spec.repeats if is_jarr else 1):
                child_id = base_job_id
                child_dir = base_trk_dir
                if is_jarr:
                    job_cp = deepcopy(job)
                    job_cp.env["GATOR_ARRAY_INDEX"] = idx_jarr
                    child_id += f"_{idx_jarr}"
                    child_dir = base_trk_dir / str(idx_jarr)
                else:
                    job_cp = job
                if isinstance(job, (JobGroup, JobArray)):
                    expected_children = job.expected_jobs
                else:
                    expected_children = 0
                child_dir.mkdir(parents=True, exist_ok=True)
                await self.db.push_childentry(
                    entry := ChildEntry(
                        ident=child_id,
                        server_url="",
                        db_file=(child_dir / "db.sqlite").as_posix(),
                        started=None,
                        stopped=None,
                        expected_children=expected_children,
                    )
                )
                grouped[job.ident].append(
                    Child(spec=job_cp, entry=entry, ident=child_id, tracking=child_dir)
                )
        # Launch or create dependencies
        async with self.lock:
            bad_deps = False
            for ident, children in grouped.items():
                spec = children[0].spec
                # If dependencies are required, form them
                if spec.on_pass or spec.on_fail or spec.on_done:
                    resolved = []
                    for dep_id in spec.on_pass + spec.on_fail + spec.on_done:
                        if dep_id not in grouped or len(grouped[dep_id]) == 0:
                            await self.logger.error(
                                f"Could not resolve dependency '{dep_id}' "
                                f"of job '{ident}', so job can never be "
                                f"launched"
                            )
                            bad_deps = True
                            break
                        resolved += grouped[dep_id]
                    # Check if a task depends on itself
                    if (
                        len({x.ident for x in children}.intersection({x.ident for x in resolved}))
                        > 0
                    ):
                        await self.logger.error(
                            f"Cannot schedule job '{ident}' as it depends on itself"
                        )
                        bad_deps = True
                    # If bad dependencies detected, break out
                    if bad_deps:
                        continue
                    # Setup a task to wait until dependencies complete
                    self.job_tasks.append(
                        asyncio.create_task(self.__postpone(ident, resolved, children))
                    )
                    # Add to the pending store
                    for child in children:
                        self.jobs_pending[child.ident] = child
                # Otherwise launch the child immediately
                else:
                    for child in children:
                        child.state = JobState.LAUNCHED
                        self.jobs_launched[child.ident] = child
            # If bad dependencies detected, stop
            if bad_deps:
                await self.logger.error("Terminating due to bad dependencies")
                self.complete = True
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
        await self.logger.info(
            f"Dependency tasks complete, waiting for "
            f"{len(all_launched)} launched jobs to complete"
        )
        await asyncio.gather(*(x.e_complete.wait() for x in all_launched))
        # Wait until complete
        await self.logger.info("Waiting for scheduler to finish")
        await self.scheduler.wait_for_all()
        # Mark complete
        self.complete = True
