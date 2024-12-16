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


import subprocess
from textwrap import dedent


def test_good_job_exit(tmp_path):
    spec_file = tmp_path / "job_good_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !Job
    ident: test_job
    command: bash
    args: [-c, exit 0]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode == 0


def test_bad_job_exit(tmp_path):
    spec_file = tmp_path / "job_bad_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !Job
    ident: test_job
    command: bash
    args: ["-c", "exit 1"]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode != 0


def test_good_array_exit(tmp_path):
    spec_file = tmp_path / "array_good_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !JobArray
    ident: test_array
    repeats: 2
    jobs:
    - !Job
        ident  : nested
        command: bash
        args: ["-c", "exit 0"]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode == 0


def test_bad_array_exit(tmp_path):
    spec_file = tmp_path / "array_bad_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !JobArray
    ident: test_array
    repeats: 2
    jobs:
    - !Job
        ident  : nested
        command: bash
        args: ["-c", "exit $GATOR_ARRAY_INDEX"]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode != 0


def test_good_group_exit(tmp_path):
    spec_file = tmp_path / "group_good_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !JobGroup
    ident: test_group
    jobs:
    - !Job
        ident  : job_a
        command: bash
        args: ["-c", "exit 0"]
    - !Job
        ident  : job_b
        command: bash
        args: ["-c", "exit 0"]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode == 0


def test_bad_group_exit(tmp_path):
    spec_file = tmp_path / "group_bad_exit.yaml"
    spec_file.write_text(
        dedent(
            """
    !JobGroup
    ident: test_group
    jobs:
    - !Job
        ident  : job_a
        command: bash
        args: ["-c", "exit 0"]
    - !Job
        ident  : job_b
        command: bash
        args: ["-c", "exit 1"]
    """
        )
    )

    proc = subprocess.run(f"python3 -m gator {spec_file}", shell=True)
    assert proc.returncode != 0
