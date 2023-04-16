from typing import Dict, List, Optional, Union

from .common import SpecBase, register
from .job import Job

@register()
class JobGroup(SpecBase):
    yaml_tag = "!JobGroup:"

    def __init__(self,
                 id   : Optional[str] = None,
                 jobs : Optional[List[Union[Job, "JobGroup"]]] = None) -> None:
        self.id = id
        self.jobs = jobs or []
