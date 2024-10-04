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

"""
Useful for when debugging issues with Gator and you need to get a view from a
layer above, can be wrapped around execution in the scheduler.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

with Path(f"log_{socket.gethostname()}_{os.getpid()}.log").open("w", encoding="utf-8") as fh:
    fh.write(f"Starting process with arguments: {sys.argv[1:]}\n")
    fh.flush()
    proc = subprocess.Popen(
        sys.argv[1:],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        fh.write(line)
        fh.flush()
    proc.wait()
    fh.write(f"Process exited with code: {proc.returncode}\n")
    fh.flush()
