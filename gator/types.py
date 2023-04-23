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


@dataclasses.dataclass
class Attribute:
    name  : str
    value : str


class LogSeverity(IntEnum):
    CRITICAL = logging.CRITICAL
    ERROR    = logging.ERROR
    WARNING  = logging.WARNING
    INFO     = logging.INFO
    DEBUG    = logging.DEBUG


@dataclasses.dataclass
class LogEntry:
    severity  : LogSeverity
    message   : str
    timestamp : datetime = dataclasses.field(default_factory=datetime.now)


@dataclasses.dataclass
class ProcStat:
    nproc     : int
    cpu       : int
    mem       : int
    vmem      : int
    timestamp : datetime = dataclasses.field(default_factory=datetime.now)
