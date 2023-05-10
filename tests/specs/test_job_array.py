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
from gator.specs.jobs import Job, JobArray, JobArray

def test_spec_job_array_positional():
    """ A job array should preserve all positional arguments provided to it """
    jobs = [Job() for _ in range(5)]
    array = JobArray("arr_123", 3, jobs)
    assert array.id == "arr_123"
    assert array.repeats == 3
    assert array.jobs == jobs

def test_spec_job_array_named():
    """ A job array should preserve all named arguments provided to it """
    jobs = [Job() for _ in range(5)]
    array = JobArray(id="arr_123", repeats=3, jobs=jobs)
    assert array.id == "arr_123"
    assert array.repeats == 3
    assert array.jobs == jobs

def test_spec_job_array_parse(tmp_path):
    """ Parse a specification from a YAML string """
    spec_file = tmp_path / "job_array.yaml"
    spec_file.write_text(
        "!JobArray\n"
        "  id: arr_123\n"
        "  repeats: 3\n"
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
        "  - !JobArray\n"
        "      id: arr_234\n"
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
    array = Spec.parse(spec_file)
    assert isinstance(array, JobArray)
    assert array.id == "arr_123"
    assert array.repeats == 3
    assert len(array.jobs) == 2
    # JOBS[0]
    assert isinstance(array.jobs[0], Job)
    assert array.jobs[0].id == "id_123"
    assert array.jobs[0].env == { "key_a": 2345, "key_b": False }
    assert array.jobs[0].cwd == "/path/to/working/dir_a"
    assert array.jobs[0].command == "echo"
    assert array.jobs[0].args == ["String to print A"]
    # JOBS[1]
    assert isinstance(array.jobs[1], JobArray)
    assert array.jobs[1].id == "arr_234"
    assert array.jobs[1].repeats == 1
    assert len(array.jobs[1].jobs) == 1
    # JOBS[1].JOBS[0]
    assert array.jobs[1].jobs[0].id == "id_234"
    assert array.jobs[1].jobs[0].env == { "key_a": 3456, "key_b": True }
    assert array.jobs[1].jobs[0].cwd == "/path/to/working/dir_b"
    assert array.jobs[1].jobs[0].command == "echo"
    assert array.jobs[1].jobs[0].args == ["String to print B"]
    # Check estimation of number of jobs to run
    assert array.expected_jobs == 6

def test_spec_job_array_parse_str():
    """ Parse a specification from a YAML string """
    spec_str = (
        "!JobArray\n"
        "  id: arr_123\n"
        "  repeats: 3\n"
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
        "  - !JobArray\n"
        "      id: arr_234\n"
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
    array = Spec.parse_str(spec_str)
    assert isinstance(array, JobArray)
    assert array.id == "arr_123"
    assert array.repeats == 3
    assert len(array.jobs) == 2
    # JOBS[0]
    assert isinstance(array.jobs[0], Job)
    assert array.jobs[0].id == "id_123"
    assert array.jobs[0].env == { "key_a": 2345, "key_b": False }
    assert array.jobs[0].cwd == "/path/to/working/dir_a"
    assert array.jobs[0].command == "echo"
    assert array.jobs[0].args == ["String to print A"]
    # JOBS[1]
    assert isinstance(array.jobs[1], JobArray)
    assert array.jobs[1].repeats == 1
    assert array.jobs[1].id == "arr_234"
    assert len(array.jobs[1].jobs) == 1
    # JOBS[1].JOBS[0]
    assert array.jobs[1].jobs[0].id == "id_234"
    assert array.jobs[1].jobs[0].env == { "key_a": 3456, "key_b": True }
    assert array.jobs[1].jobs[0].cwd == "/path/to/working/dir_b"
    assert array.jobs[1].jobs[0].command == "echo"
    assert array.jobs[1].jobs[0].args == ["String to print B"]
    # Check estimation of number of jobs to run
    assert array.expected_jobs == 6

def test_spec_job_array_dump():
    """ Dump a specification to a YAML string """
    job = Job(id     ="id_123",
              env    ={ "key_a": 2345, "key_b": False },
              cwd    ="/path/to/working/dir",
              command="echo",
              args   =["String to print"])
    grp = JobArray(id="arr_123", repeats=5, jobs=[job])
    spec_str = Spec.dump(grp)
    assert spec_str == (
        "!JobArray\n"
        "cwd: null\n"
        "env: {}\n"
        "id: arr_123\n"
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
        "repeats: 5\n"
    )
