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
import os
import sys
from typing import Dict, Union

import aiohttp


class HTTPAPI:
    """API wrapper to interface with the parent layer's server"""

    ENV_VAR = "GATOR_API"
    ROUTE_PREFIX = ""

    def __init__(self, retries: int = 10, delay: float = 0.1) -> None:
        self.retries = retries
        self.delay = delay
        self.url = os.environ.get(type(self).ENV_VAR, None)
        self.session = None

    @property
    def linked(self) -> bool:
        """Checks if a API URL has been configured"""
        return self.url is not None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def stop(self) -> None:
        await self.session.close()

    async def get(self, route: str) -> Dict[str, str]:
        """
        Perform a GET request on a route supported by the parent server.

        :param route:   Relative route to query
        :returns:       Dictionary of the response data from the server
        """
        if self.linked:
            if self.session is None:
                await self.start()
            full_url = f"http://{self.url}{self.ROUTE_PREFIX}/{route}"
            for _ in range(self.retries):
                try:
                    async with self.session.get(full_url) as resp:
                        data = await resp.json()
                        if data.get("result", None) != "success":
                            print(
                                f"Failed to GET from route '{route}' via '{self.url}'",
                                file=sys.stderr,
                            )
                        return data
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(self.delay)
            else:
                print(
                    f"Failed to GET from {full_url} after {self.retries} retries",
                    file=sys.stderr,
                )
        else:
            return {}

    async def post(self, route: str, **kwargs: Union[str, int]) -> Dict[str, str]:
        """
        Perform a POST request on a route supported by the parent server,
        attaching a JSON encoded dictionary of the keyword arguments to the query.

        :param route:       Relative route to query
        :param **kwargs:    Keyword arguments to send in the query
        :returns:           Dictionary of the response data from the server
        """
        if self.linked:
            if self.session is None:
                await self.start()
            full_url = f"http://{self.url}{self.ROUTE_PREFIX}/{route}"
            for _ in range(10):
                try:
                    async with self.session.post(full_url, json=kwargs) as resp:
                        data = await resp.json()
                        if data.get("result", None) != "success":
                            print(
                                f"Failed to POST to route '{route}' via '{self.url}'",
                                file=sys.stderr,
                            )
                        return data
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(0.1)
            else:
                print(
                    f"Failed to POST to {full_url} after {self.retries} retries",
                    file=sys.stderr,
                )
                return {}
        else:
            return {}
