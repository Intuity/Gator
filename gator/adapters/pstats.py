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

from datetime import datetime

from .parent import Parent


class ProcessStats:
    """
    Custom process statistics gathering for operations that Gator cannot normally
    track, for example launched Docker containers.

    :param ws_address: Optional websocket address for the parent tier, otherwise
                       it will be read from the GATOR_PARENT environment variable
    """

    def __init__(self, ws_address: str | None = None):
        super().__init__()
        self._parent = Parent(ws_address)

    def record(self, cpu_perc: float, memory: float):
        self._parent.post(
            "extra_usage",
            timestamp=datetime.now().timestamp(),
            cpu_perc=cpu_perc,
            memory=memory,
        )
