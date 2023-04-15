from typing import Dict, List, Optional, Union

from .common import SpecBase, register
from .job import Job

@register()
class JobGroup(SpecBase):
    yaml_tag = "!JobGroup:"

    def __init__(self,
                 id     : Optional[str] = None,
                 parent : Optional[str] = None,
                 port   : Optional[int] = None,
                 jobs   : Optional[List[Union[Job, "JobGroup"]]] = None,) -> None:
        self.id = id
        self.parent = parent
        self.port = port
        self.jobs = jobs or []
