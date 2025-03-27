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
import getpass
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

from ..common.child import Child
from ..common.logger import Logger, MessageLimits
from .common import BaseScheduler, SchedulerError
from ..specs.jobs import Job


class SlurmScheduler(BaseScheduler):
    """Executes tasks via a Slurm cluster"""

    def __init__(
        self,
        parent: str,
        interval: int = 5,
        quiet: bool = True,
        logger: Optional[Logger] = None,
        options: Optional[Dict[str, str]] = None,
        limits: Optional[MessageLimits] = None,
    ) -> None:
        super().__init__(parent, interval, quiet, logger, options, limits)
        self._username : str = getpass.getuser()
        self._api_root : str = self.get_option("api_root", "http://127.0.0.1:6820/")
        self._api_version : str | None = None
        self._token : str | None = None
        self._expiry : datetime | None = None
        self._interval : int = int(self.get_option("jwt_interval", 60))
        self._queue : str = self.get_option("queue", "generalq")
        self._job_ids : list[int] = []

    @property
    def expired(self) -> bool:
        return (self._expiry is None) or (self._expiry >= datetime.now())

    @property
    def token(self) -> str:
        if self.expired:
            result = subprocess.run(
                [
                    "scontrol",
                    "token",
                    f"lifespan={int(self._interval*1.1)}",
                    f"username={self._username}",
                ],
                capture_output=True,
                timeout=5,
                check=True,
            )
            stdout = result.stdout.decode("utf-8").strip()
            if not stdout.startswith("SLURM_JWT="):
                raise SchedulerError(f"Failed to extract Slurm JWT from STDOUT: {stdout}")
            self._token = stdout.split("SLURM_JWT=")[1].strip()
            self._expiry = datetime.now() + timedelta(seconds=self._interval)
        return self._token

    def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            base_url=self._api_root + (f"/slurm/{self._api_version}/" if self._api_version else ""),
            headers={
                "X-SLURM-USER-NAME": self._username,
                "X-SLURM-USER-TOKEN": self.token,
            }
        )

    async def launch(self, tasks: List[Child]) -> None:
        # Figure out the active API version of Slurm REST interface
        if not self._api_version:
            async with self.get_session() as session:
                async with session.get("openapi/v3") as resp:
                    data = await resp.json()
                    slurm_roots = [x for x in data["paths"] if x.startswith("/slurm/")]
                    self._api_version = Path(slurm_roots[0]).parts[2]
            await self.logger.info(f"Slurm scheduler using REST API version {self._api_version}")

        # Re-establish a session with the new API root URL
        async with self.get_session() as session:

            # Ping to check connection/authentication to Slurm
            async with session.get("ping") as resp:
                data = await resp.json()
                ping = data["pings"][0]["latency"]
                await self.logger.debug(f"Slurm REST latency {ping}")

            # For each task
            sbatch_hdr = ["#!/bin/sh", "#SBATCH"]
            for task in tasks:
                # Generate an SBATCH description
                sbatch = sbatch_hdr[:]
                if isinstance(task.spec, Job):
                    sbatch.append(f"#SBATCH --cpus-per-task={task.spec.requested_cores}")
                    sbatch.append(f"#SBATCH --mem={int(task.spec.requested_memory)}M")
                    if len(task.spec.requested_licenses) > 0:
                        sbatch.append(
                            "#SBATCH --licenses=" +
                            ",".join(f"{k}:{v}" for k, v in task.spec.requested_licenses.items())
                        )
                    if len(task.spec.requested_features) > 0:
                        sbatch.append(
                            "#SBATCH --gres=" +
                            ",".join(f"{k}:{v}" for k, v in task.spec.requested_features.items())
                        )
                sbatch.append(" ".join(self.create_command(task)))
                # Submit to slurm
                payload = {
                    "job": {
                        "script": "\n".join(sbatch) + "\n",
                        "partition": self._queue,
                        "current_working_directory": Path.cwd().as_posix(),
                        "user_id": str(os.getuid()),
                        "group_id": str(os.getgid()),
                        "environment": [f"{k}={v}" for k, v in os.environ.items()],
                    }
                }
                async with session.post("job/submit", json=payload) as resp:
                    data = await resp.json()
                    self._job_ids.append(job_id := data["result"]["job_id"])
                    await self.logger.info(f"Scheduled Slurm job {job_id}")

    async def wait_for_all(self):
        for job_id in self._job_ids:
            while True:
                states = []
                async with self.get_session() as session:
                    async with session.get(f"job/{job_id}") as resp:
                        data = await resp.json()
                        for job in data["jobs"]:
                            states += job["job_state"]
                if len([x for x in states if x.lower() in ("pending", "running")]) == 0:
                    break
                await asyncio.sleep(5)
