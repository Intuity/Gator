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

from .common import SpecBase, SpecError


class Cores(SpecBase):
    yaml_tag = "!Cores"

    def __init__(self, count : int) -> None:
        self.count = count

    def check(self) -> None:
        if not isinstance(self.count, int):
            raise SpecError(self, "count", "Count must be an integer")
        if self.count < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "count", "Count must be zero or greater")


class Memory(SpecBase):
    yaml_tag = "!Memory"

    def __init__(self, size : int, unit : str = "MB") -> None:
        self.size = size
        self.unit = unit

    @property
    def in_megabytes(self) -> int:
        mapping = { "KB": 0.1, "MB": 1, "GB": 1E3, "TB": 1E6 }.get(self.unit.strip().upper())
        return self.size * mapping

    def check(self) -> None:
        if not isinstance(self.size, int):
            raise SpecError(self, "size", "Size must be an integer")
        if self.size < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "size", "Size must be zero or greater")
        if not isinstance(self.unit, str):
            raise SpecError(self, "unit", "Unit must be a string")
        if self.unit.strip().upper() not in ("KB", "MB", "GB", "TB"):
            raise SpecError(self, "unit", f"Unknown unit '{self.unit}'")


class License(SpecBase):
    yaml_tag = "!License"

    def __init__(self, name : str, count : int = 1) -> None:
        self.name = name
        self.count = count

    def check(self) -> None:
        if not isinstance(self.name, str):
            raise SpecError(self, "name", "Name must be a string")
        if not isinstance(self.count, int):
            raise SpecError(self, "count", "Count must be an integer")
        if self.count < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "count", "Count must be zero or greater")
