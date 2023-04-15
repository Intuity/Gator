from pathlib import Path
from typing import Dict, List, Optional

import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

class JobSpec(yaml.YAMLObject):
    yaml_tag = u"!job"

    def __init__(self,
                 id : Optional[str] = None,
                 parent : Optional[str] = None,
                 port : Optional[int] = None,
                 env : Optional[Dict[str, str]] = None,
                 cwd : Optional[str] = None,
                 command : Optional[str] = None,
                 args : Optional[List[str]] = None) -> None:
        self.id = id
        self.parent = parent
        self.port = port
        self.env = env or {}
        self.cwd = cwd
        self.command = command
        self.args = args or []

    @classmethod
    def from_yaml(cls, loader, node) -> "JobSpec":
        return cls(**loader.construct_mapping(node, deep=True))

Loader.add_constructor(JobSpec.yaml_tag, JobSpec.from_yaml)

def parse_spec(path : Path) -> JobSpec:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=Loader)
