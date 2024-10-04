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

from typing import Dict

from ..common.http_api import HTTPAPI


class _HubAPI(HTTPAPI):
    ENV_VAR = "GATOR_HUB"
    ROUTE_PREFIX = "/api"
    REGISTER = "register"
    COMPLETE = "job/{job_id}/complete"
    HEARTBEAT = "job/{job_id}/heartbeat"

    async def register(self, id: str, url: str, layer: str, owner: str) -> str:
        response = await self.post(
            self.REGISTER, id=id, url=url, layer=layer, owner=owner
        )
        return response.get("uid", None)

    async def complete(self, uid: str, db_file: str) -> None:
        await self.post(self.COMPLETE.format(job_id=uid), db_file=db_file)

    async def heartbeat(self, uid: str, data: Dict[str, int]) -> None:
        await self.post(self.HEARTBEAT.format(job_id=uid), **data)


HubAPI = _HubAPI()
