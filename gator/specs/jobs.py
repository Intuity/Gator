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

import functools
from collections import Counter
from typing import Dict, List, Optional, Union

from .common import SpecBase, SpecError
from .resource import Cores, License, Memory


class Job(SpecBase):
    yaml_tag = "!Job"

    def __init__(self,
                 id        : Optional[str] = None,
                 env       : Optional[Dict[str, str]] = None,
                 cwd       : Optional[str] = None,
                 command   : Optional[str] = None,
                 args      : Optional[List[str]] = None,
                 resources : Optional[List[Union[Cores, License, Memory]]] = None,
                 on_done   : Optional[List[str]] = None,
                 on_fail   : Optional[List[str]] = None,
                 on_pass   : Optional[List[str]] = None) -> None:
        self.id = id
        self.env = env or {}
        self.cwd = cwd
        self.command = command
        self.args = args or []
        self.resources = resources or []
        self.on_done = on_done or []
        self.on_fail = on_fail or []
        self.on_pass = on_pass or []

    @property
    @functools.lru_cache()
    def requested_cores(self) -> int:
        """ Return the number of requested cores or 0 if not specified """
        for resource in self.resources:
            if isinstance(resource, Cores):
                return resource.count
        else:
            return 0

    @property
    @functools.lru_cache()
    def requested_memory(self) -> int:
        """ Return the amount of memory requested in megabytes or 0 if not specified """
        for resource in self.resources:
            if isinstance(resource, Memory):
                return resource.in_megabytes
        else:
            return 0

    @property
    @functools.lru_cache()
    def requested_licenses(self) -> Dict[str, int]:
        """ Return a summary of all of the licenses requested """
        return { x.name: x.count for x in self.resources if isinstance(x, License) }

    def check(self) -> None:
        if self.id is not None and not isinstance(self.id, str):
            raise SpecError(self, "id", "ID must be a string")
        if not isinstance(self.env, dict):
            raise SpecError(self, "env", "Environment must be a dictionary")
        if set(map(type, self.env.keys())).difference({str}):
            raise SpecError(self, "env", "Environment keys must be strings")
        if set(map(type, self.env.values())).difference({str, int}):
            raise SpecError(self, "env", "Environment values must be strings or integers")
        if self.cwd is not None and not isinstance(self.cwd, str):
            raise SpecError(self, "cwd", "Working directory must be a string")
        if self.command is not None and not isinstance(self.command, str):
            raise SpecError(self, "command", "Command must be a string")
        if not isinstance(self.args, list):
            raise SpecError(self, "args", "Arguments must be a list")
        if set(map(type, self.args)).difference({str, int}):
            raise SpecError(self, "args", "Arguments must be strings or integers")
        if not isinstance(self.resources, list):
            raise SpecError(self, "resources", "Resources must be a list")
        if set(map(type, self.resources)).difference({Cores, Memory, License}):
            raise SpecError(self, "resources", "Resources must be !Cores, !Memory, or !License")
        type_count = Counter(type(x) for x in self.resources)
        if type_count[Cores] > 1:
            raise SpecError(self, "resources", "More than one !Cores resource request")
        if type_count[Memory] > 1:
            raise SpecError(self, "resources", "More than one !Memory resource request")
        # NOTE: Any number of licenses may be specified
        lic_name_count = Counter(x.name for x in self.resources if isinstance(x, License))
        for name, count in lic_name_count.items():
            if count > 1:
                raise SpecError(self, "resources", f"More than one entry for license '{name}'")
        for field in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, field)
            if not isinstance(value, list):
                raise SpecError(self, field, f"The {field} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, field, f"The {field} entries must be strings")

class JobArray(SpecBase):
    yaml_tag = "!JobArray"

    def __init__(self,
                 id      : Optional[str] = None,
                 repeats : Optional[int] = None,
                 jobs    : Optional[List[Union[Job, "JobArray", "JobGroup"]]] = None,
                 env     : Optional[Dict[str, str]] = None,
                 cwd     : Optional[str] = None,
                 on_fail : Optional[List[str]] = None,
                 on_pass : Optional[List[str]] = None,
                 on_done : Optional[List[str]] = None) -> None:
        self.id = id
        self.repeats = 1 if (repeats is None) else repeats
        self.jobs = jobs or []
        self.env = env or {}
        self.cwd = cwd
        self.on_fail = on_fail or []
        self.on_pass = on_pass or []
        self.on_done = on_done or []

    @property
    @functools.lru_cache()
    def expected_jobs(self) -> int:
        expected = 0
        for job in self.jobs:
            expected += self.repeats * (1 if isinstance(job, Job) else job.expected_jobs)
        return expected

    def check(self) -> None:
        if self.id is not None and not isinstance(self.id, str):
            raise SpecError(self, "id", "ID must be a string")
        if not isinstance(self.repeats, int) or self.repeats < 0:
            raise SpecError(self, "repeats", "Repeats must be a positive integer")
        if not isinstance(self.jobs, list):
            raise SpecError(self, "jobs", "Jobs must be a list")
        if set(map(type, self.jobs)).difference({Job, JobArray, JobGroup}):
            raise SpecError(self, "jobs", "Expecting a list of only Job, JobArray, and JobGroup")
        id_count = Counter(x.id for x in self.jobs)
        duplicated = [k for k, v in id_count.items() if v > 1]
        if duplicated:
            raise SpecError(self, "jobs", f"Duplicated keys for jobs: {', '.join(duplicated)}")
        if not isinstance(self.env, dict):
            raise SpecError(self, "env", "Environment must be a dictionary")
        if set(map(type, self.env.keys())).difference({str}):
            raise SpecError(self, "env", "Environment keys must be strings")
        if set(map(type, self.env.values())).difference({str, int}):
            raise SpecError(self, "env", "Environment values must be strings or integers")
        if self.cwd is not None and not isinstance(self.cwd, str):
            raise SpecError(self, "cwd", "Working directory must be a string")
        for field in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, field)
            if not isinstance(value, list):
                raise SpecError(self, field, f"The {field} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, field, f"The {field} entries must be strings")
        # Recurse
        for job in self.jobs:
            job.check()


class JobGroup(SpecBase):
    yaml_tag = "!JobGroup"

    def __init__(self,
                 id      : Optional[str] = None,
                 jobs    : Optional[List[Union[Job, "JobGroup", JobArray]]] = None,
                 env     : Optional[Dict[str, str]] = None,
                 cwd     : Optional[str] = None,
                 on_fail : Optional[List[str]] = None,
                 on_pass : Optional[List[str]] = None,
                 on_done : Optional[List[str]] = None) -> None:
        self.id = id
        self.jobs = jobs or []
        self.env = env or {}
        self.cwd = cwd
        self.on_fail = on_fail or []
        self.on_pass = on_pass or []
        self.on_done = on_done or []

    @property
    @functools.lru_cache()
    def expected_jobs(self) -> int:
        expected = 0
        for job in self.jobs:
            expected += 1 if isinstance(job, Job) else job.expected_jobs
        return expected

    def check(self) -> None:
        if self.id is not None and not isinstance(self.id, str):
            raise SpecError(self, "id", "ID must be a string")
        if not isinstance(self.jobs, list):
            raise SpecError(self, "jobs", "Jobs must be a list")
        if set(map(type, self.jobs)).difference({Job, JobArray, JobGroup}):
            raise SpecError(self, "jobs", "Expecting a list of only Job, JobArray, and JobGroup")
        id_count = Counter(x.id for x in self.jobs)
        duplicated = [k for k, v in id_count.items() if v > 1]
        if duplicated:
            raise SpecError(self, "jobs", f"Duplicated keys for jobs: {', '.join(duplicated)}")
        if not isinstance(self.env, dict):
            raise SpecError(self, "env", "Environment must be a dictionary")
        if set(map(type, self.env.keys())).difference({str}):
            raise SpecError(self, "env", "Environment keys must be strings")
        if set(map(type, self.env.values())).difference({str, int}):
            raise SpecError(self, "env", "Environment values must be strings or integers")
        if self.cwd is not None and not isinstance(self.cwd, str):
            raise SpecError(self, "cwd", "Working directory must be a string")
        for field in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, field)
            if not isinstance(value, list):
                raise SpecError(self, field, f"The {field} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, field, f"The {field} entries must be strings")
        # Recurse
        for job in self.jobs:
            job.check()
