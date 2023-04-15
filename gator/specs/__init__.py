from pathlib import Path

import yaml

from .common import Dumper, Loader, SpecBase
from .job import Job
from .job_group import JobGroup

assert all((Job, JobGroup))

class Spec:

    @staticmethod
    def parse(path : Path) -> SpecBase:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.load(fh, Loader=Loader)

    @staticmethod
    def parse_str(data : str) -> SpecBase:
        return yaml.load(data, Loader=Loader)

    @staticmethod
    def dump(object : SpecBase) -> str:
        return yaml.dump(object, Dumper=Dumper)
