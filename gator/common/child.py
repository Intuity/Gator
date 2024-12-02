# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
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
from pathlib import Path
from typing import Optional, Union

from ..specs import Job, JobArray, JobGroup
from .summary import Summary, make_summary
from .types import ChildEntry, JobState
from .ws_wrapper import WebsocketWrapper


@dataclass
class Child:
    spec: Union[Job, JobArray, JobGroup]
    ident: str
    entry: ChildEntry
    tracking: Optional[Path] = None
    state: JobState = JobState.PENDING
    exitcode: int = 0

    # Tracking of the state of the child tree and metrics
    summary: Summary = field(default_factory=make_summary)

    # Complete Event
    e_complete: asyncio.Event = field(default_factory=asyncio.Event)

    # Socket
    ws: Optional[WebsocketWrapper] = None
