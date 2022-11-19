import os
import time

import click
import requests

class Logger:
    INST = None

    def __init__(self):
        self.parent = os.environ.get("GATOR_PARENT", None)

    @classmethod
    def instance(cls):
        if cls.INST is None:
            cls.INST = cls()
        return cls.INST

    def _log(self, severity, message):
        resp = requests.post("http://" + self.parent + "/log",
                             json={"timestamp": time.time(),
                                   "severity" : severity.upper(),
                                   "message"  : message})
        if resp.json().get("result", None) != "success":
            print(f"Failed to log via {self.parent}")

    @staticmethod
    def debug(message):
        return Logger.instance()._log("DEBUG", message)

    @staticmethod
    def info(message):
        return Logger.instance()._log("INFO", message)

    @staticmethod
    def warning(message):
        return Logger.instance()._log("WARNING", message)

    @staticmethod
    def error(message):
        return Logger.instance()._log("ERROR", message)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    Logger.instance()._log(severity, message)

if __name__ == "__main__":
    logger(prog_name="logger")
