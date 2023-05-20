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

def test_spec_job_positional():
    """ A job should preserve all positional arguments provided to it """
    job = Job("id_123",
              { "key_a": 2345, "key_b": False },
              "/path/to/working/dir",
              "echo",
              ["String to print"])
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]

def test_spec_job_named():
    """ A job should preserve all named arguments provided to it """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"])
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]

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
    )
    job = Spec.parse(spec_file)
    assert isinstance(job, Job)
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]

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
    )
    job = Spec.parse_str(spec_str)
    assert isinstance(job, Job)
    assert job.id == "id_123"
    assert job.env == { "key_a": 2345, "key_b": False }
    assert job.cwd == "/path/to/working/dir"
    assert job.command == "echo"
    assert job.args == ["String to print"]

def test_spec_job_dump():
    """ Dump a specification to a YAML string """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"])
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
        "on_done: []\n"
        "on_fail: []\n"
        "on_pass: []\n"
        "resources: []\n"
    )

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
