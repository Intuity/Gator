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

from pathlib import Path

import click

from .layer import Layer
from .parent import Parent
from .specs import Job, JobGroup, Spec
from .wrapper import Wrapper


@click.command()
@click.option("--id",       default=None,  type=str,          help="Instance identifier")
@click.option("--parent",   default=None,  type=str,          help="Pointer to parent node")
@click.option("--interval", default=5,     type=int,          help="Polling interval", show_default=True)
@click.option("--tracking", default=None,  type=click.Path(), help="Tracking directory")
@click.option("--quiet",    default=False, count=True,        help="Silence STDOUT logging")
@click.argument("spec", type=click.Path(exists=True), required=False)
def launch(id : str, parent : str, interval : int, tracking : str, quiet : bool, spec : str) -> None:
    if parent:
        Parent.parent = parent
    # Work out where the spec is coming from
    if spec:
        spec_obj = Spec.parse(Path(spec))
    elif Parent.linked and id:
        spec_obj = Parent.spec(id)
    else:
        raise Exception("No specification file provided and no parent server to query")
    # Map tracking directory
    tracking = Path(tracking) if tracking else (Path.cwd() / "tracking")
    # If a JobGroup is provided, launch a layer
    if isinstance(spec_obj, JobGroup):
        Layer(spec    =spec_obj,
              tracking=tracking,
              quiet   =quiet)
    # If a Job is provided, launch a wrapper
    elif isinstance(spec_obj, Job):
        Wrapper(spec    =spec_obj,
                tracking=tracking,
                interval=interval,
                quiet   =quiet)
    # Unsupported forms
    else:
        raise Exception(f"Unsupported specification object of type {type(spec_obj).__name__}")

if __name__ == "__main__":
    launch(prog_name="gator", auto_envvar_prefix="GATOR_")
