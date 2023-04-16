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

from gator.specs.job import Job
from gator.specs import Spec

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

def test_spec_job_parse():
    """ Parse a specification from a YAML string """
    spec_str = (
        "!Job:\n"
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
    """ Dump a specifcation to a YAML string """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"])
    spec_str = Spec.dump(job)
    assert spec_str == (
        "!Job:\n"
        "args:\n"
        "- String to print\n"
        "command: echo\n"
        "cwd: /path/to/working/dir\n"
        "env:\n"
        "  key_a: 2345\n"
        "  key_b: false\n"
        "id: id_123\n"
    )
