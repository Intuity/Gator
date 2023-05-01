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

from pathlib import Path

from ..common.http_api import HTTPAPI

class _HubAPI(HTTPAPI):
    ENV_VAR      = "GATOR_HUB"
    ROUTE_PREFIX = "/api"
    REGISTER     = Path("register")

    def register(self, id : str, url : str) -> None:
        response = self.post(self.REGISTER, id=id, url=url)
        print(f"Registration UID {response['uid']}")
        return response.get("uid", None)

HubAPI = _HubAPI()
