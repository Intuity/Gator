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

from dataclasses import dataclass

from .common import SpecBase, SpecError


ARCH_ALIASES = {
    # x86
    "x86": "x86_64",
    "x86_64": "x86_64",
    "amd64": "x86_64",
    # Arm
    "arm": "aarch64",
    "arm64": "aarch64",
    "aarch64": "aarch64",
    # RISC-V
    "riscv": "riscv64",
    "riscv64": "riscv64",
}


@dataclass
class Cores(SpecBase):
    """
    Specifies the count and optionally the architecture of the CPU cores to
    execute on
    """
    yaml_tag = "!Cores"

    count: int
    arch: str | None

    def check(self) -> None:
        if not isinstance(self.count, int):
            raise SpecError(self, "count", "Count must be an integer")
        if self.count < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "count", "Count must be zero or greater")
        if self.arch is not None:
            if not isinstance(self.arch, str):
                raise SpecError(self, "arch", "Architecture must be a string")
            self.arch = self.arch.lower().strip()
            if self.arch not in ARCH_ALIASES:
                raise SpecError(self, "arch", f"Architecture must be one of {', '.join(ARCH_ALIASES)}")
            self.arch = ARCH_ALIASES[self.arch]


@dataclass
class Memory(SpecBase):
    """Specifies the quantity of memory (RAM) required for the job to execute"""
    yaml_tag = "!Memory"

    size: int
    unit: str = "MB"

    @property
    def in_megabytes(self) -> int:
        mapping = {"KB": 0.1, "MB": 1, "GB": 1e3, "TB": 1e6}.get(self.unit.strip().upper())
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


@dataclass
class License(SpecBase):
    """
    Specifies a floating license required for a job to run, if the license is
    node-locked then a !Feature should be used instead.
    """
    yaml_tag = "!License"

    name: str
    count: int = 1

    def check(self) -> None:
        if not isinstance(self.name, str):
            raise SpecError(self, "name", "Name must be a string")
        if not isinstance(self.count, int):
            raise SpecError(self, "count", "Count must be an integer")
        if self.count < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "count", "Count must be zero or greater")


@dataclass
class Feature(SpecBase):
    """
    Specifies a feature of a machine required for a job to run, this can be used
    for describing node-locked licenses or accelerators.
    """
    yaml_tag = "!Feature"

    name: str
    count: int = 1

    def check(self) -> None:
        if not isinstance(self.name, str):
            raise SpecError(self, "name", "Name must be a string")
        if not isinstance(self.count, int):
            raise SpecError(self, "count", "Count must be an integer")
        if self.count < 0:
            # NOTE: Zero is valid - if a job doesn't consume much resource then
            #       it may be desirable to run it without blocking others
            raise SpecError(self, "count", "Count must be zero or greater")
