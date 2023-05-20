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

import yaml
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

class SpecBase(yaml.YAMLObject):
    yaml_tag    = "!unset"
    yaml_loader = Loader
    yaml_dumper = Dumper

    @classmethod
    def from_yaml(cls, loader : Loader, node : yaml.Node) -> "SpecBase":
        if isinstance(node, yaml.nodes.MappingNode):
            return cls(**loader.construct_mapping(node, deep=True))
        else:
            return cls(*loader.construct_sequence(node))

    def check(self) -> None:
        pass

class SpecError(Exception):
    """ Custom exception type for syntax errors in specifications """

    def __init__(self, obj : SpecBase, field : str, msg : str) -> None:
        super().__init__(msg)
        self.obj = obj
        self.field = field
