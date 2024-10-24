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

import dataclasses
import logging
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Dict, Optional, Sequence, TypedDict, Union

from .db import Base


class LogSeverity(IntEnum):
    """Log severity levels matched to Python's defaults"""

    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG


class Result(IntEnum):
    """Status of a job"""

    UNKNOWN = 0
    SUCCESS = 1
    FAILURE = 2


@dataclasses.dataclass
class Attribute(Base):
    """General purpose attribute"""

    name: str = ""
    value: str = ""


@dataclasses.dataclass
class LogEntry(Base):
    """Single log message"""

    severity: LogSeverity = LogSeverity.INFO
    message: str = ""
    timestamp: datetime = dataclasses.field(default_factory=datetime.now)


@dataclasses.dataclass
class ProcStat(Base):
    """Process resource usage object"""

    nproc: int = 0
    cpu: int = 0
    mem: int = 0
    vmem: int = 0
    timestamp: datetime = dataclasses.field(default_factory=datetime.now)


class _MetricScopeEnum(StrEnum):
    OWN = "_OWN_"
    GROUP = "_GROUP_"


MetricScope = Union[_MetricScopeEnum, str]


@dataclasses.dataclass
class Metric(Base):
    """General purpose numeric (integer) metric"""

    Scope = _MetricScopeEnum

    scope: MetricScope = Scope.OWN
    name: str = ""
    value: int = 0


@dataclasses.dataclass
class ChildEntry(Base):
    """General purpose attribute"""

    ident: str = ""
    server_url: str = ""
    db_file: Optional[str] = None
    start: Optional[float] = None
    stop: Optional[float] = None


class JobState(StrEnum):
    PENDING = "pending"
    LAUNCHED = "launched"
    STARTED = "started"
    COMPLETE = "complete"


Metrics = Dict[str, int]


class ApiResolvable(TypedDict):
    "Minimal data required to resolve a job either via websocket or database"

    status: JobState
    server_url: str
    db_file: str


class ApiJob(TypedDict):
    "Resolved job API response"

    uidx: int
    ident: str
    status: JobState
    metrics: Metrics
    server_url: str
    db_file: str
    owner: Optional[str]
    start: Optional[float]
    stop: Optional[float]


class ChildrenResponse(TypedDict):
    "Resolved children API response"

    status: JobState
    jobs: Sequence[ApiJob]


class LayerResponse(ApiJob, ChildrenResponse):
    "Resolved layer (job + children) API response"

    ...
