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

import asyncio
import signal
from pathlib import Path
from typing import Callable, Optional, Union

from rich.console import Console

from .common.logger import Logger
from .common.ws_client import WebsocketClient
from .layer import Layer
from .specs import Job, JobArray, JobGroup, Spec
from .wrapper import Wrapper


async def launch(id           : Optional[str]               = None,
                 spec         : Optional[Union[Spec, Path]] = None,
                 tracking     : Path                        = Path.cwd(),
                 interval     : int                         = 5,
                 quiet        : bool                        = False,
                 all_msg      : bool                        = False,
                 heartbeat_cb : Optional[Callable]          = None,
                 console      : Optional[Console]           = None) -> None:
    # If a console isn't given, create one
    if not console:
        console = Console(log_path=False)
        console.log("Starting Gator :crocodile:")
    # Ensure logger has a pointer to the console
    Logger.set_console(console)
    # Start client
    await WebsocketClient.start()
    # Work out where the spec is coming from
    if spec is None and WebsocketClient.linked and id:
        raw_spec = await WebsocketClient.spec(id=id)
        spec     = Spec.parse_str(raw_spec.get("spec", ""))
    elif spec is not None and not isinstance(spec, Spec):
        spec = Spec.parse(Path(spec))
    else:
        raise Exception("No specification file provided and no parent server to query")
    # If an ID has been provided, override whatever the spec gives
    if id is not None:
        spec.id = id
    # If a JobArray or JobGroup is provided, launch a layer
    if isinstance(spec, (JobArray, JobGroup)):
        top = Layer(spec        =spec,
                    tracking    =tracking,
                    quiet       =quiet and not all_msg,
                    all_msg     =all_msg,
                    heartbeat_cb=heartbeat_cb)
    # If a Job is provided, launch a wrapper
    elif isinstance(spec, Job):
        top = Wrapper(spec    =spec,
                      tracking=tracking,
                      interval=interval,
                      quiet   =quiet and not all_msg)
    # Unsupported forms
    else:
        raise Exception(f"Unsupported specification object of type {type(spec).__name__}")
    # Setup signal handler to capture CTRL+C events
    def _handler(sig : signal, evt_loop : asyncio.BaseEventLoop, top : Union[Layer, Wrapper]):
        if top.is_root:
            evt_loop.create_task(top.stop())
    evt_loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        evt_loop.add_signal_handler(sig, lambda: _handler(sig, evt_loop, top))
    # Wait for the executor to complete
    await top.launch()
    # Shutdown client
    await WebsocketClient.stop()
