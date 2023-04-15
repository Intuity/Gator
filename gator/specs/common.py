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
    def _inner(obj : Type[SpecBase]) -> Type[SpecBase]:
        assert issubclass(obj, SpecBase)
        obj.yaml_tag = f"!{tag}:" if tag else f"!{obj.__name__}:"
        return obj
    return _inner
