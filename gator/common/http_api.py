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
from pathlib import Path
from typing import Dict, Union

import requests
from requests.adapters import HTTPAdapter, Retry


class HTTPAPI:
    """ API wrapper to interface with the parent layer's server """

    ENV_VAR = "GATOR_API"
    ROUTE_PREFIX = ""

    def __init__(self) -> None:
        self.url = os.environ.get(type(self).ENV_VAR, None)
        self.session = requests.Session()
        self.session.mount("http://", HTTPAdapter(max_retries=Retry(total=5,
                                                                    backoff_factor=0.1)))

    @property
    def linked(self) -> bool:
        """ Checks if a API URL has been configured """
        return self.url is not None

    def get(self, route : Union[str, Path]) -> Dict[str, str]:
        """
        Perform a GET request on a route supported by the parent server.

        :param route:   Relative route to query
        :returns:       Dictionary of the response data from the server
        """
        if self.linked:
            if isinstance(route, Path):
                route = route.as_posix()
            resp = requests.get(f"http://{self.url}{self.ROUTE_PREFIX}/{route}")
            data = resp.json()
            if data.get("result", None) != "success":
                print(f"Failed to GET from route '{route}' via '{self.url}'", file=sys.stderr)
            return data
        else:
            return {}

    def post(self, route : Union[str, Path], **kwargs : Dict[str, Union[str, int]]) -> Dict[str, str]:
        """
        Perform a POST request on a route supported by the parent server,
        attaching a JSON encoded dictionary of the keyword arguments to the query.

        :param route:       Relative route to query
        :param **kwargs:    Keyword arguments to send in the query
        :returns:           Dictionary of the response data from the server
        """
        if self.linked:
            if isinstance(route, Path):
                route = route.as_posix()
            resp = requests.post(f"http://{self.url}{self.ROUTE_PREFIX}/{route}", json=kwargs)
            data = resp.json()
            if data.get("result", None) != "success":
                print(f"Failed to POST to route '{route}' via '{self.url}'", file=sys.stderr)
            return data
        else:
            return {}
