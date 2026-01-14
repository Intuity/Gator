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
import os
import platform
import signal
import socket
from functools import partial
from pathlib import Path
from typing import Dict, Optional, Type, Union, cast

from rich.console import Console

from .common.layer import HeartbeatCb
from .common.logger import Logger, MessageLimits
from .common.summary import Summary
from .common.types import LogSeverity
from .common.ws_client import WebsocketClient
from .hub.api import HubAPI
from .scheduler import LocalScheduler
from .specs import Job, JobArray, JobGroup, Spec
from .specs.common import SpecBase
from .tier import Tier
from .wrapper import Wrapper


async def launch(
    ident: Optional[str] = None,
    hub: Optional[str] = None,
    parent: Optional[str] = None,
    spec: Optional[Union[SpecBase, Spec, Path]] = None,
    tracking: Optional[Path] = None,
    interval: int = 5,
    quiet: bool = False,
    all_msg: bool = False,
    verbose: bool = False,
    heartbeat_cb: Optional[HeartbeatCb] = None,
    console: Optional[Console] = None,
    scheduler: Type = LocalScheduler,
    sched_opts: Optional[Dict[str, str]] = None,
    glyph: Optional[str] = None,
    limits: Optional[MessageLimits] = None,
    internal: bool = False,
) -> Summary:
    # Glyph only used when progress bar visible
    del glyph
    # Set the hub URL
    HubAPI.url = hub
    # Set the default tracking path
    tracking = Path.cwd() if tracking is None else tracking
    # If a console isn't given, create one
    if not console:
        console = Console(log_path=False)
        console.log("Starting Gator :crocodile:")
    # Start client
    client = WebsocketClient(address=parent)
    await client.start()
    # Create a logger with a pointer to the console
    logger = Logger(
        ws_cli=client,
        verbosity=[LogSeverity.INFO, LogSeverity.DEBUG][verbose],
        forward=all_msg,
    )
    logger.set_console(console)
    # Log the machine's details
    uname = platform.uname()
    await logger.info(
        f"Running on {socket.getfqdn()} as PID {os.getpid()} under {Path.cwd()} "
        f"(architecture: {uname.processor}, OS: {uname.system} {uname.release})"
    )
    # Work out where the spec is coming from
    # - From server (nested call)
    parsed_spec: SpecBase
    if spec is None and client.linked and ident:
        raw_spec = await client.spec(ident=ident)
        parsed_spec = Spec.parse_str(raw_spec.get("spec", ""))
    # - Passed in directly (when used as a library
    elif spec is not None and isinstance(spec, (Job, JobArray, JobGroup)):
        parsed_spec = cast(SpecBase, spec)
    # - Passed as a file path
    elif spec is not None and isinstance(spec, (Path, str)):
        parsed_spec = Spec.parse(Path(spec))
    # - Unknown
    else:
        raise Exception("No specification file provided and no parent server to query")

    # Hint for the type checker and a safety during debugging
    assert isinstance(parsed_spec, Job | JobArray | JobGroup), \
        ("Expected specification to be a Job, JobArray or JobGroup, received "
         f"{type(parsed_spec).__name__}."
        )

    # If an ident has been provided, override whatever the spec gives
    if ident is not None:
        parsed_spec.ident = ident

    # Check the spec object
    parsed_spec.check()

    # When user launches a single job, wrap it up in a JobArray so we can
    # launch it via a common mechanism (which will ensure this job launches via
    # the specified scheduler)
    if isinstance(parsed_spec, Job) and not internal:
        parsed_spec = JobArray(jobs=[parsed_spec])

    if isinstance(parsed_spec, Job) and internal:
        # Internal single job - launch via the wrapper on current machine
        # as this is the executor instance. I.e. don't use the scheduler
        top = Wrapper(
            spec=parsed_spec,
            client=client,
            logger=logger,
            tracking=tracking,
            interval=interval,
            quiet=quiet and not all_msg,
            all_msg=all_msg,
            heartbeat_cb=heartbeat_cb,
            limits=limits,
        )
    else:
        # Non-internal single job or a multi-task job - launch via the scheduler
        top = Tier(
            spec=parsed_spec,
            client=client,
            logger=logger,
            tracking=tracking,
            interval=interval,
            quiet=quiet and not all_msg,
            all_msg=all_msg,
            heartbeat_cb=heartbeat_cb,
            scheduler=scheduler,
            sched_opts=sched_opts,
            limits=limits,
        )

    # Setup signal handler to capture CTRL+C events
    def _handler(sig: signal, evt_loop: asyncio.BaseEventLoop, top: Union[Tier, Wrapper]):
        if top.is_root:
            evt_loop.create_task(top.stop())

    evt_loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        evt_loop.add_signal_handler(sig, partial(_handler, sig, evt_loop, top))
    # Wait for the executor to complete
    await top.launch()
    # Calculate final summary
    summary = await top.summarise()
    # Log out failures
    if failed_ids := summary.failed_ids:
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
