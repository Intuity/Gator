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
from dataclasses import dataclass, field
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from typing import Dict, Union, Optional

from .ws_wrapper import WebsocketWrapper
from ..specs import Job, JobArray, JobGroup
from .types import Metric, Result

class ChildState(Enum):
    PENDING  = auto()
    LAUNCHED = auto()
    STARTED  = auto()
    COMPLETE = auto()

@dataclass
class Child:
    spec       : Union[Job, JobArray, JobGroup]
    id         : str               = "N/A"
    tracking   : Optional[Path]    = None
    state      : ChildState        = ChildState.PENDING
    result     : Result            = Result.UNKNOWN
    server     : str               = ""
    exitcode   : int               = 0
    # Metric tracking
    metrics    : Dict[str, Metric] = field(default_factory=dict)
    # Tracking of the state of the child tree
    sub_total  : int               = 0
    sub_active : int               = 0
    sub_passed : int               = 0
    sub_failed : int               = 0
    # Timestamping
    started    : datetime          = field(default_factory=lambda: datetime.fromtimestamp(0))
    updated    : datetime          = field(default_factory=lambda: datetime.fromtimestamp(0))
    completed  : datetime          = field(default_factory=lambda: datetime.fromtimestamp(0))
    e_complete : asyncio.Event     = field(default_factory=asyncio.Event)
    # Socket
    ws         : Optional[WebsocketWrapper] = None
