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
import math
import signal
from pathlib import Path
from typing import Callable, Optional, Type, Union

from rich.console import Console

from .common.logger import Logger, MessageLimits
from .common.types import LogSeverity
from .common.ws_client import WebsocketClient
from .hub.api import HubAPI
from .tier import Tier
from .scheduler import LocalScheduler
from .specs import Job, JobArray, JobGroup, Spec
from .wrapper import Wrapper


async def launch(
    id           : Optional[str]               = None,
    hub          : Optional[str]               = None,
    parent       : Optional[str]               = None,
    spec         : Optional[Union[Spec, Path]] = None,
    tracking     : Path                        = Path.cwd(),
    interval     : int                         = 5,
    quiet        : bool                        = False,
    all_msg      : bool                        = False,
    verbose      : bool                        = False,
    heartbeat_cb : Optional[Callable]          = None,
    console      : Optional[Console]           = None,
    scheduler    : Type                        = LocalScheduler,
    sched_opts   : Optional[dict[str, str]]    = None,
    glyph        : str | None                  = None,
    limits       : MessageLimits | None        = None,
) -> dict:
    # Glyph only used when progress bar visible
    del glyph
    # Set the hub URL
    HubAPI.url = hub
    # If a console isn't given, create one
    if not console:
        console = Console(log_path=False)
        console.log("Starting Gator :crocodile:")
    # Start client
    client = WebsocketClient(address=parent)
    await client.start()
    # Create a logger with a pointer to the console
    logger = Logger(ws_cli   =client,
                    verbosity=[LogSeverity.INFO, LogSeverity.DEBUG][verbose],
                    forward  =all_msg)
    logger.set_console(console)
    # Work out where the spec is coming from
    # - From server (nested call)
    if spec is None and client.linked and id:
        raw_spec = await client.spec(id=id)
        spec     = Spec.parse_str(raw_spec.get("spec", ""))
    # - Passed in directly (when used as a library
    elif spec is not None and isinstance(spec, (Job, JobArray, JobGroup)):
        pass
    # - Passed as a file path
    elif spec is not None and isinstance(spec, (Path, str)):
        spec = Spec.parse(Path(spec))
    # - Unknown
    else:
        raise Exception("No specification file provided and no parent server to query")
    # If an ID has been provided, override whatever the spec gives
    if id is not None:
        spec.id = id
    # Check the spec object
    spec.check()
    # If a JobArray or JobGroup is provided, launch a tier
    if isinstance(spec, (JobArray, JobGroup)):
        top = Tier(spec        =spec,
                   client      =client,
                   logger      =logger,
                   tracking    =tracking,
                   quiet       =quiet and not all_msg,
                   all_msg     =all_msg,
                   heartbeat_cb=heartbeat_cb,
                   scheduler   =scheduler,
                   sched_opts  =sched_opts,
                   limits      =limits)
    # If a Job is provided, launch a wrapper
    elif isinstance(spec, Job):
        top = Wrapper(spec    =spec,
                      client  =client,
                      logger  =logger,
                      tracking=tracking,
                      interval=interval,
                      quiet   =quiet and not all_msg,
                      limits  =limits)
    # Unsupported forms
    else:
        raise Exception(f"Unsupported specification object of type {type(spec).__name__}")
    # Setup signal handler to capture CTRL+C events
    def _handler(sig : signal, evt_loop : asyncio.BaseEventLoop, top : Union[Tier, Wrapper]):
        if top.is_root:
            evt_loop.create_task(top.stop())
    evt_loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        evt_loop.add_signal_handler(sig, lambda: _handler(sig, evt_loop, top))
    # Wait for the executor to complete
    await top.launch()
    # Calculate final summary
    summary = await top.summarise()
    # Log out failures
    if (failed_ids := summary.get("failed_ids", [])):
        msg = f"In this hierarchy {len(failed_ids)} jobs failed: "
        for idx, f_id in enumerate(failed_ids):
            entry = f"[{idx:0{math.ceil(math.log(len(failed_ids)))}d}] {'.'.join(f_id)}"
            if idx == 0:
                console.log(msg + entry)
            else:
                console.log(f"{' '*len(msg)}{entry}")
    # Shutdown client
    await client.stop()
    # Return summary
    return summary
