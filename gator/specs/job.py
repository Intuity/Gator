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

from typing import Dict, List, Optional

from .common import SpecBase, register

@register()
class Job(SpecBase):
    yaml_tag = "!Job"

    def __init__(self,
                 id      : Optional[str] = None,
                 env     : Optional[Dict[str, str]] = None,
                 cwd     : Optional[str] = None,
                 command : Optional[str] = None,
                 args    : Optional[List[str]] = None) -> None:
        self.id = id
        self.env = env or {}
        self.cwd = cwd
        self.command = command
        self.args = args or []
