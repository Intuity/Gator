from typing import List
import subprocess

class Scheduler:
    """ Launches a set of tasks on a particular infrastructure """

    def __init__(self, tasks : List[str], parent : str, interval : int = 5) -> None:
        self.tasks    = tasks
        self.parent   = parent
        self.interval = interval
        self.state    = {}
        self.launch()

    def launch(self):
        common = ["python3", "-m", "gator",
                  "--parent", self.parent,
                  "--quiet",
                  "--interval", f"{self.interval}"]
        for task in self.tasks:
            self.state[task] = subprocess.Popen(common + ["--id", f"{task}"],
                                                stdin =subprocess.DEVNULL,
                                                stdout=subprocess.DEVNULL)

    def wait_for_all(self):
        for proc in self.state.values():
            proc.wait()
