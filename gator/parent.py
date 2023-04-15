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

import os
import sys
from typing import Dict

import requests

from .specs import Spec

class _Parent:

    def __init__(self):
        self.parent = os.environ.get("GATOR_PARENT", None)

    @property
    def linked(self):
        return self.parent is not None

    def get(self, route) -> Dict:
        if self.linked:
            resp = requests.get(f"http://{self.parent}/{route}")
            data = resp.json()
            if data.get("result", None) != "success":
                print(f"Failed to GET from route '{route}' via '{self.parent}'", file=sys.stderr)
            return data
        else:
            return {}

    def post(self, route, **kwargs) -> Dict:
        if self.linked:
            resp = requests.post(f"http://{self.parent}/{route}", json=kwargs)
            data = resp.json()
            if data.get("result", None) != "success":
                print(f"Failed to post to route '{route}' via '{self.parent}'", file=sys.stderr)
            return data
        else:
            return {}

    def spec(self, id):
        return Spec.parse_str(self.get(f"children/{id}").get("spec", ""))

    def register(self, id, server):
        self.post(f"children/{id}", server=server)

    def complete(self, id, exit_code, warnings, errors):
        self.post(f"children/{id}/complete", code=exit_code, warnings=warnings, errors=errors)

    def update(self, id, warnings, errors):
        self.post(f"children/{id}/update", warnings=warnings, errors=errors)

Parent = _Parent()
