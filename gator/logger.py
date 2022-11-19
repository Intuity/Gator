import os
import logging
import time

import click
import requests

from .parent import Parent

class Logger:

    @staticmethod
    def _log(severity, message):
        if Parent.linked:
            Parent.post("log", timestamp=time.time(),
                               severity =severity.upper(),
                               message  =message)
        else:
            logging.log(logging._nameToLevel.get(severity, None), message)

    @staticmethod
    def debug(message):
        return Logger._log("DEBUG", message)

    @staticmethod
    def info(message):
        return Logger._log("INFO", message)

    @staticmethod
    def warning(message):
        return Logger._log("WARNING", message)

    @staticmethod
    def error(message):
        return Logger._log("ERROR", message)

@click.command()
@click.option("-s", "--severity", type=str, default="INFO", help="Severity level")
@click.argument("message")
def logger(severity, message):
    Logger._log(severity, message)

if __name__ == "__main__":
    logger(prog_name="logger")
