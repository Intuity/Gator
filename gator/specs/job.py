from typing import Dict, List, Optional

from .common import SpecBase, register

@register()
class Job(SpecBase):
    yaml_tag = "!Job:"

    def __init__(self,
                 id      : Optional[str] = None,
                 env     : Optional[Dict[str, str]] = None,
                 cwd     : Optional[str] = None,
                 command : Optional[str] = None,
                 args    : Optional[List[str]] = None) -> None:
        self.id = id
        self.env = env or {}
        self.cwd = cwd
        self.command = command
        self.args = args or []
