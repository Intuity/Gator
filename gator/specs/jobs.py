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
from typing import Dict, List, Optional, Union

from .common import SpecBase


class Job(SpecBase):
    yaml_tag = "!Job"

    def __init__(self,
                 id      : Optional[str] = None,
                 env     : Optional[Dict[str, str]] = None,
                 cwd     : Optional[str] = None,
                 command : Optional[str] = None,
                 args    : Optional[List[str]] = None,
                 on_fail : Optional[List[str]] = None,
                 on_pass : Optional[List[str]] = None,
                 on_done : Optional[List[str]] = None) -> None:
        self.id = id
        self.env = env or {}
        self.cwd = cwd
        self.command = command
        self.args = args or []
        self.on_fail = on_fail or []
        self.on_pass = on_pass or []
        self.on_done = on_done or []


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
