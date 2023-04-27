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

from typing import List
import subprocess

class Scheduler:
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self,
                 tasks    : List[str],
                 parent   : str,
                 interval : int = 5,
                 quiet    : bool = True) -> None:
        self.tasks    = tasks
        self.parent   = parent
        self.interval = interval
        self.quiet    = quiet
        self.state    = {}
        self.launch()

    def launch(self):
        common = ["python3", "-m", "gator",
                  "--parent", self.parent,
                  "--interval", f"{self.interval}",
                  ["--all-msg", "--quiet"][self.quiet]]
        for task in self.tasks:
            self.state[task] = subprocess.Popen(common + ["--id", f"{task}"],
                                                stdin =subprocess.DEVNULL,
                                                stdout=subprocess.DEVNULL)

    def wait_for_all(self):
        for proc in self.state.values():
            proc.wait()
