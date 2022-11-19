import os
import socket
import subprocess
from pathlib import Path
from typing import Optional

import click

from .db import Database
from .server import Server

class Layer:
    """ Layer of the process tree """

    def __init__(self,
                 id       : Optional[str] = None,
                 parent   : Optional[str] = None,
                 port     : Optional[int] = None,
                 tracking : Path = Path.cwd() / "tracking") -> None:
        self.id       = id or os.getpid()
        self.parent   = parent
        self.tracking = tracking
        # Setup database and server
        self.db     = Database(self.tracking / f"{self.id}.db")
        self.server = Server(port, self.db)
        self.launch()
        self.db.stop()

    def launch(self):
        # TODO: Currently using a fixed subprocess set
        print("Launch tasks")
        procs = []
        for idx in range(5):
            procs.append(subprocess.Popen(["python3", "-m", "gator.wrapper",
                                                      "--gator-interval", "1",
                                                      "--gator-plotting", f"res_{idx}.png",
                                                      "--gator-parent", f"{socket.gethostname()}:{self.server.port}",
                                                      "--gator-id", f"sub_{idx}",
                                                      "./test_sh.sh",
                                                      "10"],
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL))
        # Wait for subprocesses to complete
        print(f"Wait for {len(procs)} tasks")
        for proc in procs:
            proc.wait()
        print("All tasks complete")


@click.command()
@click.option("--gator-id",       default=None, type=str, help="Job identifier")
@click.option("--gator-parent",   default=None, type=str, help="Parent's server")
@click.option("--gator-port",     default=None, type=int, help="Port number for server")
@click.option("--gator-tracking", default=None, type=str, help="Tracking directory")
def layer(gator_id, gator_parent, gator_port, gator_tracking):
    kwargs = {}
    if gator_port is not None:
        kwargs["port"] = int(gator_port)
    if gator_tracking is not None:
        kwargs["tracking"] = Path(gator_tracking)
    Layer(gator_id, gator_parent, **kwargs)

if __name__ == "__main__":
    layer(prog_name="layer", default_map={
        f"gator_{k[6:].lower()}": v
        for k, v in os.environ.items() if k.startswith("GATOR_")
    })
