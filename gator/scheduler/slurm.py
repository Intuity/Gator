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
from enum import IntEnum
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import aiohttp

from ..common.child import Child
from ..common.logger import Logger, MessageLimits
from .common import BaseScheduler, SchedulerError
from ..specs.jobs import Job


class SlurmErrorCodes(IntEnum):
    """Enumerates common Slurm error codes"""
    INVALID_TRES_SPEC: int = 2115
    """Invalid Trackable RESource (TRES) specification"""
    SLURMDB_CONN_FAIL: int = 7000
    """Unable to connect to database (slurmdb connection failure)"""



class SlurmScheduler(BaseScheduler):
    """Executes tasks via a Slurm cluster"""

    RETRY_ON_ERROR : ClassVar[set[int]] = {
        SlurmErrorCodes.SLURMDB_CONN_FAIL,
    }

    def __init__(
        self,
        tracking: Path,
        parent: str,
        interval: int = 5,
        quiet: bool = True,
        logger: Optional[Logger] = None,
        options: Optional[Dict[str, str]] = None,
        limits: Optional[MessageLimits] = None,
    ) -> None:
        super().__init__(tracking, parent, interval, quiet, logger, options, limits)
        self._username : str = getpass.getuser()
        self._api_root : str = self.get_option("api_root", "http://127.0.0.1:6820/")
        self._api_version : str | None = None
        self._token : str | None = None
        self._expiry : datetime | None = None
        self._interval : int = int(self.get_option("jwt_interval", 60))
        self._queue : str = self.get_option("queue", "generalq")
        self._job_ids : list[int] = []
        self._stdout_dirx : Path = self.tracking / "slurm"
        self._stdout_dirx.mkdir(exist_ok=True, parents=True)

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

    def clear_token(self):
        self._token = None
        self._expiry = None

    def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            base_url=self._api_root + (f"/slurm/{self._api_version}/" if self._api_version else ""),
            headers={
                "X-SLURM-USER-NAME": self._username,
                "X-SLURM-USER-TOKEN": self.token,
            }
        )

    async def _retry_post(
        self,
        route: str,
        payload: dict[str, str],
        retries: int = 3,
        backoff: float = 1.0,
    ) -> dict[str, str]:
        for idx in range(retries):
            async with self.get_session() as session:
                async with session.post(route, json=payload) as resp:
                    data = await resp.json()
                    err_nums = [x.get("error_number", None) for x in data.get("errors", [])]
                    # Check for a known error
                    if set(err_nums).intersection(self.RETRY_ON_ERROR):
                        # Log what happened
                        await self.logger.debug(
                            f"Slurm API error on attempt {idx}/{retries}, retrying "
                            f"in {backoff} seconds (with forced token refresh)"
                        )
                        # Force a token expiry
                        self.clear_token()
                        # Wait a little
                        await asyncio.sleep(backoff)
                        # Retry
                        continue
                    # If no known error, return the data
                    return data
        else:
            raise SchedulerError(
                f"Post request to {route} failed {retries} times: {data}"
            )

    async def _retry_get(
        self,
        route: str,
        retries: int = 3,
        backoff: float = 1.0,
    ) -> dict[str, str]:
        for idx in range(retries):
            async with self.get_session() as session:
                async with session.get(route) as resp:
                    data = await resp.json()
                    err_nums = [x.get("error_number", None) for x in data.get("errors", [])]
                    # Check for a known error
                    if set(err_nums).intersection(self.RETRY_ON_ERROR):
                        # Log what happened
                        await self.logger.debug(
                            f"Slurm API error on attempt {idx}/{retries}, retrying "
                            f"in {backoff} seconds (with forced token refresh)"
                        )
                        # Force a token expiry
                        self.clear_token()
                        # Wait a little
                        await asyncio.sleep(backoff)
                        # Retry
                        continue
                    # If no known error, return the data
                    return data
        else:
            raise SchedulerError(
                f"Post request to {route} failed {retries} times: {data}"
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

        # Ping to check connection/authentication to Slurm
        data = await self._retry_get("ping")
        ping = data["pings"][0]["latency"]
        await self.logger.debug(f"Slurm REST latency {ping}")

        # For each task...
        for idx, task in enumerate(tasks):
            # Figure out the requested resources
            tres_per_job = []
            if isinstance(task.spec, Job):
                tres_per_job += [
                    f"cpu={int(task.spec.requested_cores)}",
                    f"mem={int(task.spec.requested_memory)}",
                    *[f"license/{k}={v}" for k, v in task.spec.requested_licenses.items()],
                    *[f"gres/{k}={v}" for k, v in task.spec.requested_features.items()],
                ]

            # Submit the payload to Slurm
            stdout = self._stdout_dirx / f"{task.ident}.log"
            data = await self._retry_post("job/submit", {
                "job": {
                    "name": task.ident,
                    "script": "\n".join([
                        "#!/bin/bash",
                        " ".join(self.create_command(task)) + f" | tee {os.getcwd()}/task_{idx}.log",
                        "",
                    ]),
                    "tres_per_job": ",".join(tres_per_job),
                    "partition": self._queue,
                    "current_working_directory": Path.cwd().as_posix(),
                    "user_id": str(os.getuid()),
                    "group_id": str(os.getgid()),
                    "environment": [f"{k}={v}" for k, v in os.environ.items()],
                    "standard_output": stdout.as_posix(),
                    "standard_error": stdout.as_posix(),
                }
            })

            # Check for an invalid request
            err_codes = {
                x.get("error_number", 0) for x in data.get("errors", []) if
                (x.get("error_number", 0) != 0)
            }
            if err_codes.intersection({ SlurmErrorCodes.INVALID_TRES_SPEC }):
                raise SchedulerError(
                    f"Gator generated an unsupported resource request to Slurm "
                    f"({data['errors'][0]['error']}): {tres_per_job}"
                )
            elif len(err_codes) > 0:
                raise SchedulerError(
                    "Gator received unexpected error(s) when submitting a job "
                    "to Slurm: " +
                    ", ".join(f"{x['error']} ({x['error_number']})" for x in data["errors"])
                )

            # Track the job ID
            self._job_ids.append(job_id := data["result"]["job_id"])
            await self.logger.debug(f"Scheduled Slurm job {job_id}")

    async def wait_for_all(self):
        for job_id in self._job_ids:
            while True:
                states = []
                data = await self._retry_get(f"job/{job_id}")
                for job in data["jobs"]:
                    states += job["job_state"]
                if len([x for x in states if x.lower() in ("pending", "running")]) == 0:
                    break
                await asyncio.sleep(5)
