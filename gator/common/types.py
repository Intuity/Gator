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
from enum import IntEnum
from datetime import datetime

from .db import Base


class LogSeverity(IntEnum):
    """ Log severity levels matched to Python's defaults """
    CRITICAL = logging.CRITICAL
    ERROR    = logging.ERROR
    WARNING  = logging.WARNING
    INFO     = logging.INFO
    DEBUG    = logging.DEBUG


class Result(IntEnum):
    """ Status of a job """
    UNKNOWN = 0
    SUCCESS = 1
    FAILURE = 2


@dataclasses.dataclass
class Attribute(Base):
    """ General purpose attribute """
    name  : str = ""
    value : str = ""


@dataclasses.dataclass
class LogEntry(Base):
    """ Single log message """
    severity  : LogSeverity = LogSeverity.INFO
    message   : str         = ""
    timestamp : datetime    = dataclasses.field(default_factory=datetime.now)


@dataclasses.dataclass
class ProcStat(Base):
    """ Process resource usage object """
    nproc     : int      = 0
    cpu       : int      = 0
    mem       : int      = 0
    vmem      : int      = 0
    timestamp : datetime = dataclasses.field(default_factory=datetime.now)


@dataclasses.dataclass
class Metric(Base):
    """ General purpose numeric (integer) metric """
    name  : str = ""
    value : int = 0
