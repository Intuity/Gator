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
from typing import Union, Optional

from .ws_wrapper import WebsocketWrapper
from ..specs import Job, JobArray, JobGroup

class ChildState(Enum):
    LAUNCHED = auto()
    STARTED  = auto()
    COMPLETE = auto()

@dataclass
class Child:
    spec       : Union[Job, JobArray, JobGroup]
    id         : str            = "N/A"
    tracking   : Optional[Path] = None
    state      : ChildState     = ChildState.LAUNCHED
    server     : str            = ""
    exitcode   : int            = 0
    # Message counting
    warnings   : int            = 0
    errors     : int            = 0
    # Tracking of childrens' state
    sub_total  : int            = 0
    sub_active : int            = 0
    sub_passed : int            = 0
    sub_failed : int            = 0
    # Timestamping
    started    : datetime       = datetime.min
    updated    : datetime       = datetime.min
    completed  : datetime       = datetime.min
    e_complete : asyncio.Event  = field(default_factory=asyncio.Event)
    # Socket
    ws         : Optional[WebsocketWrapper] = None
