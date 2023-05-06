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

from gator.specs import Spec
from gator.specs.jobs import Job, JobGroup

def test_spec_job_group_positional():
    """ A job group should preserve all positional arguments provided to it """
    jobs = [Job() for _ in range(5)]
    group = JobGroup("grp_123", jobs)
    assert group.id == "grp_123"
    assert group.jobs == jobs

def test_spec_job_named():
    """ A job group should preserve all named arguments provided to it """
    jobs = [Job() for _ in range(5)]
    group = JobGroup(id="grp_123", jobs=jobs)
    assert group.id == "grp_123"
    assert group.jobs == jobs

def test_spec_job_group_parse(tmp_path):
    """ Parse a specification from a YAML string """
    spec_file = tmp_path / "job_group.yaml"
    spec_file.write_text(
        "!JobGroup\n"
        "  id: grp_123\n"
        "  jobs:\n"
        "  - !Job\n"
        "      id: id_123\n"
        "      env:\n"
        "        key_a: 2345\n"
        "        key_b: False\n"
        "      cwd: /path/to/working/dir_a\n"
        "      command: echo\n"
        "      args:\n"
        "        - String to print A\n"
        "  - !JobGroup\n"
        "      id: grp_234\n"
        "      jobs: \n"
        "      - !Job\n"
        "          id: id_234\n"
        "          env:\n"
        "            key_a: 3456\n"
        "            key_b: True\n"
        "          cwd: /path/to/working/dir_b\n"
        "          command: echo\n"
        "          args:\n"
        "            - String to print B\n"
    )
    group = Spec.parse(spec_file)
    assert isinstance(group, JobGroup)
    assert group.id == "grp_123"
    assert len(group.jobs) == 2
    # JOBS[0]
    assert isinstance(group.jobs[0], Job)
    assert group.jobs[0].id == "id_123"
    assert group.jobs[0].env == { "key_a": 2345, "key_b": False }
    assert group.jobs[0].cwd == "/path/to/working/dir_a"
    assert group.jobs[0].command == "echo"
    assert group.jobs[0].args == ["String to print A"]
    # JOBS[1]
    assert isinstance(group.jobs[1], JobGroup)
    assert group.jobs[1].id == "grp_234"
    assert len(group.jobs[1].jobs) == 1
    # JOBS[1].JOBS[0]
    assert group.jobs[1].jobs[0].id == "id_234"
    assert group.jobs[1].jobs[0].env == { "key_a": 3456, "key_b": True }
    assert group.jobs[1].jobs[0].cwd == "/path/to/working/dir_b"
    assert group.jobs[1].jobs[0].command == "echo"
    assert group.jobs[1].jobs[0].args == ["String to print B"]

def test_spec_job_group_parse_str():
    """ Parse a specification from a YAML string """
    spec_str = (
        "!JobGroup\n"
        "  id: grp_123\n"
        "  jobs:\n"
        "  - !Job\n"
        "      id: id_123\n"
        "      env:\n"
        "        key_a: 2345\n"
        "        key_b: False\n"
        "      cwd: /path/to/working/dir_a\n"
        "      command: echo\n"
        "      args:\n"
        "        - String to print A\n"
        "  - !JobGroup\n"
        "      id: grp_234\n"
        "      jobs: \n"
        "      - !Job\n"
        "          id: id_234\n"
        "          env:\n"
        "            key_a: 3456\n"
        "            key_b: True\n"
        "          cwd: /path/to/working/dir_b\n"
        "          command: echo\n"
        "          args:\n"
        "            - String to print B\n"
    )
    group = Spec.parse_str(spec_str)
    assert isinstance(group, JobGroup)
    assert group.id == "grp_123"
    assert len(group.jobs) == 2
    # JOBS[0]
    assert isinstance(group.jobs[0], Job)
    assert group.jobs[0].id == "id_123"
    assert group.jobs[0].env == { "key_a": 2345, "key_b": False }
    assert group.jobs[0].cwd == "/path/to/working/dir_a"
    assert group.jobs[0].command == "echo"
    assert group.jobs[0].args == ["String to print A"]
    # JOBS[1]
    assert isinstance(group.jobs[1], JobGroup)
    assert group.jobs[1].id == "grp_234"
    assert len(group.jobs[1].jobs) == 1
    # JOBS[1].JOBS[0]
    assert group.jobs[1].jobs[0].id == "id_234"
    assert group.jobs[1].jobs[0].env == { "key_a": 3456, "key_b": True }
    assert group.jobs[1].jobs[0].cwd == "/path/to/working/dir_b"
    assert group.jobs[1].jobs[0].command == "echo"
    assert group.jobs[1].jobs[0].args == ["String to print B"]

def test_spec_job_group_dump():
    """ Dump a specification to a YAML string """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"])
    grp = JobGroup(id="grp_123", jobs=[job])
    spec_str = Spec.dump(grp)
    assert spec_str == (
        "!JobGroup\n"
        "cwd: null\n"
        "env: {}\n"
        "id: grp_123\n"
        "jobs:\n"
        "- !Job\n"
        "  args:\n"
        "  - String to print\n"
        "  command: echo\n"
        "  cwd: /path/to/working/dir\n"
        "  env:\n"
        "    key_a: 2345\n"
        "    key_b: false\n"
        "  id: id_123\n"
        "  on_done: []\n"
        "  on_fail: []\n"
        "  on_pass: []\n"
        "on_done: []\n"
        "on_fail: []\n"
        "on_pass: []\n"
    )
