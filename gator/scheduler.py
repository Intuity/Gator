from dataclasses import dataclass
from typing import Dict, List
import subprocess

from .wrapper import Wrapper

@dataclass
class Task:
    id       : str
    cmd      : List[str]
    interval : int = 5

class Scheduler:
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self, tasks : List[Task], parent : str) -> None:
        self.tasks  = tasks
        self.parent = parent
        self.state  = {}
        self.launch()

    def launch(self):
        for task in self.tasks:
            cmd  = ["python3", "-m", "gator.wrapper"]
            cmd += ["--gator-id", task.id]
            cmd += ["--gator-parent", self.parent]
            cmd += ["--gator-interval", str(task.interval)]
            cmd += ["--gator-quiet"]
            cmd += task.cmd
            self.state[task.id] = subprocess.Popen(cmd,
                                                   stdin =subprocess.DEVNULL,
                                                   stdout=subprocess.DEVNULL)

    def wait_for_all(self):
        for proc in self.state.values():
            proc.wait()
