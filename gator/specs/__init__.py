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

import yaml

from .common import Dumper, Loader, SpecBase
from .jobs import Job, JobArray, JobGroup
from .resource import Cores, License, Memory

assert all((Job, JobArray, JobGroup, Cores, License, Memory))

class Spec:
    """ Methods to parse and dump YAML specification objects """

    @staticmethod
    def parse(path : Path) -> SpecBase:
        """
        Parse a YAML file from disk and return any spec object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed spec object
        """
        with path.open("r", encoding="utf-8") as fh:
            return yaml.load(fh, Loader=Loader)

    @staticmethod
    def parse_str(data : str) -> SpecBase:
        """
        Parse a YAML string and return any spec object it contains.

        :param data: YAML string
        :returns:    Parsed spec object
        """
        return yaml.load(data, Loader=Loader)

    @staticmethod
    def dump(object : SpecBase) -> str:
        """
        Dump a spec object into a YAML string

        :param object: Spec object to dump
        :returns:      YAML string representation
        """
        return yaml.dump(object, Dumper=Dumper)
