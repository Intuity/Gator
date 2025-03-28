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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from .common import SpecBase, SpecError
from .resource import Cores, License, Memory, Feature


@dataclass
class Job(SpecBase):
    yaml_tag = "!Job"

    ident: Optional[str] = None
    env: Optional[Dict[str, str]] = field(default_factory=dict)
    cwd: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = field(default_factory=list)
    resources: Optional[List[Union[Cores, License, Memory, Feature]]] = field(default_factory=list)
    on_done: Optional[List[str]] = field(default_factory=list)
    on_fail: Optional[List[str]] = field(default_factory=list)
    on_pass: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        self.cwd = self.cwd or (self.yaml_path.parent.as_posix() if self.yaml_path else None)

    @functools.cached_property
    def requested_cores(self) -> int:
        """Return the number of requested cores or 0 if not specified"""
        for resource in self.resources:
            if isinstance(resource, Cores):
                return resource.count
        else:
            return 0

    @functools.cached_property
    def requested_memory(self) -> int:
        """Return the amount of memory requested in megabytes or 0 if not specified"""
        for resource in self.resources:
            if isinstance(resource, Memory):
                return resource.in_megabytes
        else:
            return 0

    @functools.cached_property
    def requested_licenses(self) -> Dict[str, int]:
        """Return a summary of all of the licenses requested"""
        return {x.name: x.count for x in self.resources if isinstance(x, License)}

    @functools.cached_property
    def requested_features(self) -> Dict[str, int]:
        """Return a summary of all of the features requested"""
        return {x.name: x.count for x in self.resources if isinstance(x, Feature)}

    def check(self) -> None:
        if self.ident is not None and not isinstance(self.ident, str):
            raise SpecError(self, "ident", "ident must be a string")
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
        if set(map(type, self.resources)).difference({Cores, Memory, License, Feature}):
            raise SpecError(
                self,
                "resources",
                "Resources must be !Cores, !Memory, !License, or !Feature",
            )
        type_count = Counter(type(x) for x in self.resources)
        if type_count[Cores] > 1:
            raise SpecError(self, "resources", "More than one !Cores resource request")
        if type_count[Memory] > 1:
            raise SpecError(self, "resources", "More than one !Memory resource request")
        # NOTE: Any number of licenses may be specified
        lic_name_count = Counter(x.name for x in self.resources if isinstance(x, License))
        for name, count in lic_name_count.items():
            if count > 1:
                raise SpecError(
                    self,
                    "resources",
                    f"More than one entry for license '{name}'",
                )
        # NOTE: Any number of features may be specified
        feat_name_count = Counter(x.name for x in self.resources if isinstance(x, Feature))
        for name, count in feat_name_count.items():
            if count > 1:
                raise SpecError(
                    self,
                    "resources",
                    f"More than one entry for feature '{name}'",
                )
        for condition in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, condition)
            if not isinstance(value, list):
                raise SpecError(self, condition, f"The {condition} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, condition, f"The {condition} entries must be strings")


@dataclass
class JobArray(SpecBase):
    yaml_tag = "!JobArray"

    ident: Optional[str] = None
    repeats: Optional[int] = 1
    jobs: Optional[List[Union[Job, "JobArray", "JobGroup"]]] = field(default_factory=list)
    env: Optional[Dict[str, str]] = field(default_factory=dict)
    cwd: Optional[str] = None
    on_fail: Optional[List[str]] = field(default_factory=list)
    on_pass: Optional[List[str]] = field(default_factory=list)
    on_done: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        self.cwd = self.cwd or (self.yaml_path.parent.as_posix() if self.yaml_path else None)

    @functools.cached_property
    def expected_jobs(self) -> int:
        expected = 0
        for job in self.jobs:
            expected += self.repeats * (1 if isinstance(job, Job) else job.expected_jobs)
        return expected

    def check(self) -> None:
        if self.ident is not None and not isinstance(self.ident, str):
            raise SpecError(self, "ident", "ident must be a string")
        if not isinstance(self.repeats, int) or self.repeats < 0:
            raise SpecError(self, "repeats", "Repeats must be a positive integer")
        if not isinstance(self.jobs, list):
            raise SpecError(self, "jobs", "Jobs must be a list")
        if set(map(type, self.jobs)).difference({Job, JobArray, JobGroup}):
            raise SpecError(
                self,
                "jobs",
                "Expecting a list of only Job, JobArray, and JobGroup",
            )
        id_count = Counter(x.ident for x in self.jobs)
        duplicated = [k for k, v in id_count.items() if v > 1]
        if duplicated:
            raise SpecError(
                self,
                "jobs",
                f"Duplicated keys for jobs: {', '.join(duplicated)}",
            )
        if not isinstance(self.env, dict):
            raise SpecError(self, "env", "Environment must be a dictionary")
        if set(map(type, self.env.keys())).difference({str}):
            raise SpecError(self, "env", "Environment keys must be strings")
        if set(map(type, self.env.values())).difference({str, int}):
            raise SpecError(self, "env", "Environment values must be strings or integers")
        if self.cwd is not None and not isinstance(self.cwd, str):
            raise SpecError(self, "cwd", "Working directory must be a string")
        for condition in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, condition)
            if not isinstance(value, list):
                raise SpecError(self, condition, f"The {condition} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, condition, f"The {condition} entries must be strings")
        # Recurse
        for job in self.jobs:
            job.check()


@dataclass
class JobGroup(SpecBase):
    yaml_tag = "!JobGroup"

    ident: Optional[str] = None
    jobs: Optional[List[Union[Job, "JobArray", "JobGroup"]]] = field(default_factory=list)
    env: Optional[Dict[str, str]] = field(default_factory=dict)
    cwd: Optional[str] = None
    on_fail: Optional[List[str]] = field(default_factory=list)
    on_pass: Optional[List[str]] = field(default_factory=list)
    on_done: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        self.cwd = self.cwd or (self.yaml_path.parent.as_posix() if self.yaml_path else None)

    @functools.cached_property
    def expected_jobs(self) -> int:
        expected = 0
        for job in self.jobs:
            expected += 1 if isinstance(job, Job) else job.expected_jobs
        return expected

    def check(self) -> None:
        if self.ident is not None and not isinstance(self.ident, str):
            raise SpecError(self, "ident", "ident must be a string")
        if not isinstance(self.jobs, list):
            raise SpecError(self, "jobs", "Jobs must be a list")
        if set(map(type, self.jobs)).difference({Job, JobArray, JobGroup}):
            raise SpecError(
                self,
                "jobs",
                "Expecting a list of only Job, JobArray, and JobGroup",
            )
        id_count = Counter(x.ident for x in self.jobs)
        duplicated = [k for k, v in id_count.items() if v > 1]
        if duplicated:
            raise SpecError(
                self,
                "jobs",
                f"Duplicated keys for jobs: {', '.join(duplicated)}",
            )
        if not isinstance(self.env, dict):
            raise SpecError(self, "env", "Environment must be a dictionary")
        if set(map(type, self.env.keys())).difference({str}):
            raise SpecError(self, "env", "Environment keys must be strings")
        if set(map(type, self.env.values())).difference({str, int}):
            raise SpecError(self, "env", "Environment values must be strings or integers")
        if self.cwd is not None and not isinstance(self.cwd, str):
            raise SpecError(self, "cwd", "Working directory must be a string")
        for condition in ("on_done", "on_fail", "on_pass"):
            value = getattr(self, condition)
            if not isinstance(value, list):
                raise SpecError(self, condition, f"The {condition} dependencies must be a list")
            if set(map(type, value)).difference({str}):
                raise SpecError(self, condition, f"The {condition} entries must be strings")
        # Recurse
        for job in self.jobs:
            job.check()
