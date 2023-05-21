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

import pytest

from gator.specs import Spec
from gator.specs.common import SpecError
from gator.specs.jobs import Job
from gator.specs.resource import Cores, License, Memory

def test_spec_job_positional():
    """ A job should preserve all positional arguments provided to it """
    job = Job("id_123",
              { "key_a": 2345, "key_b": False },
              "/path/to/working/dir",
              "echo",
              ["String to print"],
              [Cores(3), License("A", 2), Memory(1, "GB")],
              ["job_0"],
              ["job_1"],
              ["job_2"])
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]
    assert isinstance(job.resources[0], Cores)
    assert job.resources[0].count == 3
    assert job.requested_cores == 3
    assert isinstance(job.resources[1], License)
    assert job.resources[1].name == "A"
    assert job.resources[1].count == 2
    assert job.requested_licenses == {"A": 2}
    assert isinstance(job.resources[2], Memory)
    assert job.resources[2].size == 1
    assert job.resources[2].unit == "GB"
    assert job.requested_memory == 1000
    assert job.on_done == ["job_0"]
    assert job.on_fail == ["job_1"]
    assert job.on_pass == ["job_2"]

def test_spec_job_named():
    """ A job should preserve all named arguments provided to it """
    job = Job(id       ="id_123",
              env      ={ "key_a": 2345, "key_b": False },
              cwd      ="/path/to/working/dir",
              command  ="echo",
              args     =["String to print"],
              resources=[Cores(3), License("A", 2), Memory(1, "GB")],
              on_done  =["job_0"],
              on_fail  =["job_1"],
              on_pass  =["job_2"])
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]
    assert isinstance(job.resources[0], Cores)
    assert job.resources[0].count == 3
    assert job.requested_cores == 3
    assert isinstance(job.resources[1], License)
    assert job.resources[1].name == "A"
    assert job.resources[1].count == 2
    assert job.requested_licenses == {"A": 2}
    assert isinstance(job.resources[2], Memory)
    assert job.resources[2].size == 1
    assert job.resources[2].unit == "GB"
    assert job.requested_memory == 1000
    assert job.on_done == ["job_0"]
    assert job.on_fail == ["job_1"]
    assert job.on_pass == ["job_2"]

def test_spec_job_parse(tmp_path):
    """ Parse a specification from a YAML file """
    spec_file = tmp_path / "job.yaml"
    spec_file.write_text(
        "!Job\n"
        "  id: id_123\n"
        "  env:\n"
        "    key_a: 2345\n"
        "    key_b: False\n"
        "  cwd: /path/to/working/dir\n"
        "  command: echo\n"
        "  args:\n"
        "    - String to print\n"
        "  resources:\n"
        "    - !Cores [3]\n"
        "    - !License [A, 2]\n"
        "    - !Memory [1, GB]\n"
        "  on_done:\n"
        "    - job_0\n"
        "  on_fail:\n"
        "    - job_1\n"
        "  on_pass:\n"
        "    - job_2\n"
    )
    job = Spec.parse(spec_file)
    assert isinstance(job, Job)
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]
    assert isinstance(job.resources[0], Cores)
    assert job.resources[0].count == 3
    assert job.requested_cores == 3
    assert isinstance(job.resources[1], License)
    assert job.resources[1].name == "A"
    assert job.resources[1].count == 2
    assert job.requested_licenses == {"A": 2}
    assert isinstance(job.resources[2], Memory)
    assert job.resources[2].size == 1
    assert job.resources[2].unit == "GB"
    assert job.requested_memory == 1000
    assert job.on_done == ["job_0"]
    assert job.on_fail == ["job_1"]
    assert job.on_pass == ["job_2"]

def test_spec_job_parse_str():
    """ Parse a specification from a YAML string """
    spec_str = (
        "!Job\n"
        "  id: id_123\n"
        "  env:\n"
        "    key_a: 2345\n"
        "    key_b: False\n"
        "  cwd: /path/to/working/dir\n"
        "  command: echo\n"
        "  args:\n"
        "    - String to print\n"
        "  resources:\n"
        "    - !Cores [3]\n"
        "    - !License [A, 2]\n"
        "    - !Memory [1, GB]\n"
        "  on_done:\n"
        "    - job_0\n"
        "  on_fail:\n"
        "    - job_1\n"
        "  on_pass:\n"
        "    - job_2\n"
    )
    job = Spec.parse_str(spec_str)
    assert isinstance(job, Job)
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]
    assert isinstance(job.resources[0], Cores)
    assert job.resources[0].count == 3
    assert job.requested_cores == 3
    assert isinstance(job.resources[1], License)
    assert job.resources[1].name == "A"
    assert job.resources[1].count == 2
    assert job.requested_licenses == {"A": 2}
    assert isinstance(job.resources[2], Memory)
    assert job.resources[2].size == 1
    assert job.resources[2].unit == "GB"
    assert job.requested_memory == 1000
    assert job.on_done == ["job_0"]
    assert job.on_fail == ["job_1"]
    assert job.on_pass == ["job_2"]

def test_spec_job_dump():
    """ Dump a specification to a YAML string """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"],
              resources=[Cores(3), License("A", 2), Memory(1, "GB")],
              on_done  =["job_0"],
              on_fail  =["job_1"],
              on_pass  =["job_2"])
    spec_str = Spec.dump(job)
    assert spec_str == (
        "!Job\n"
        "args:\n"
        "- String to print\n"
        "command: echo\n"
        "cwd: /path/to/working/dir\n"
        "env:\n"
        "  key_a: 2345\n"
        "  key_b: false\n"
        "id: id_123\n"
        "on_done:\n"
        "- job_0\n"
        "on_fail:\n"
        "- job_1\n"
        "on_pass:\n"
        "- job_2\n"
        "resources:\n"
        "- !Cores\n"
        "  count: 3\n"
        "- !License\n"
        "  count: 2\n"
        "  name: A\n"
        "- !Memory\n"
        "  size: 1\n"
        "  unit: GB\n"
    )

def test_spec_job_default_resources():
    """
    Zero should be returned for cores and memory and an empty dictionary for
    licenses
    """
    job = Job()
    assert job.requested_cores == 0
    assert job.requested_memory == 0
    assert job.requested_licenses == {}

def test_spec_job_bad_fields():
    """ Bad field values should be flagged """
    # Check ID
    with pytest.raises(SpecError) as exc:
        Job(id=123).check()
    assert str(exc.value) == "ID must be a string"
    assert exc.value.field == "id"
    # Check environment (non-dictionary)
    with pytest.raises(SpecError) as exc:
        Job(env=[1, 2, 3]).check()
    assert str(exc.value) == "Environment must be a dictionary"
    assert exc.value.field == "env"
    # Check environment (non-string keys)
    with pytest.raises(SpecError) as exc:
        Job(env={True: 123, False: 345}).check()
    assert str(exc.value) == "Environment keys must be strings"
    assert exc.value.field == "env"
    # Check environment (non-string/integer values)
    with pytest.raises(SpecError) as exc:
        Job(env={"hi": 123.23, "bye": False}).check()
    assert str(exc.value) == "Environment values must be strings or integers"
    assert exc.value.field == "env"
    # Check CWD
    with pytest.raises(SpecError) as exc:
        Job(cwd=123).check()
    assert str(exc.value) == "Working directory must be a string"
    assert exc.value.field == "cwd"
    # Check command
    with pytest.raises(SpecError) as exc:
        Job(command=123).check()
    assert str(exc.value) == "Command must be a string"
    assert exc.value.field == "command"
    # Check arguments (non-list)
    with pytest.raises(SpecError) as exc:
        Job(args={ "a": 123 }).check()
    assert str(exc.value) == "Arguments must be a list"
    assert exc.value.field == "args"
    # Check arguments (non-string/integer values)
    with pytest.raises(SpecError) as exc:
        Job(args=[123.1, False]).check()
    assert str(exc.value) == "Arguments must be strings or integers"
    assert exc.value.field == "args"
    # Check bad resources (non-list)
    with pytest.raises(SpecError) as exc:
        Job(resources=Cores(2)).check()
    assert str(exc.value) == "Resources must be a list"
    assert exc.value.field == "resources"
    # Check bad resources (non-YAML tags)
    with pytest.raises(SpecError) as exc:
        Job(resources=["hello", 2]).check()
    assert str(exc.value) == "Resources must be !Cores, !Memory, or !License"
    assert exc.value.field == "resources"
    # Check duplicate entries for !Cores
    with pytest.raises(SpecError) as exc:
        Job(resources=[Cores(2), Cores(1)]).check()
    assert str(exc.value) == "More than one !Cores resource request"
    assert exc.value.field == "resources"
    # Check duplicate entries for !Memory
    with pytest.raises(SpecError) as exc:
        Job(resources=[Memory(2), Memory(1)]).check()
    assert str(exc.value) == "More than one !Memory resource request"
    assert exc.value.field == "resources"
    # Check duplicate entries of a particular license
    with pytest.raises(SpecError) as exc:
        Job(resources=[Cores(2), License("A"), License("B"), License("B")]).check()
    assert str(exc.value) == "More than one entry for license 'B'"
    assert exc.value.field == "resources"
    # Check on done/fail/pass
    for field in ("on_done", "on_fail", "on_pass"):
        # Check non-list
        with pytest.raises(SpecError) as exc:
            Job(**{field: {"a": 1}}).check()
        assert str(exc.value) == f"The {field} dependencies must be a list"
        assert exc.value.field == field
        # Check non-string values
        with pytest.raises(SpecError) as exc:
            Job(**{field: [123.2, False]}).check()
        assert str(exc.value) == f"The {field} entries must be strings"
        assert exc.value.field == field
