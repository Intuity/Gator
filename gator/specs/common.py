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

from typing import Callable, Type

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
        return cls(**loader.construct_mapping(node, deep=True))


def register(tag : str = None) -> Callable:
    """
    Decorator used to register a YAML spec object by setting the 'yaml_tag' to
    match the name of the class.

    :param tag: Optionally provide the name of the tag, otherwise registered
                using the class name
    :returns:   Inner decorating method
    """
    def _inner(obj : Type[SpecBase]) -> Type[SpecBase]:
        assert issubclass(obj, SpecBase)
        obj.yaml_tag = f"!{tag}" if tag else f"!{obj.__name__}"
        return obj
    return _inner
