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

from datetime import datetime

import pytest

from gator.common.db import Query
from gator.types import Attribute, LogEntry, LogSeverity, ProcStat

from .common.test_db import database

assert all((database, ))

@pytest.mark.asyncio
class TestTypes:

    async def test_attribute(self, database):
        """ Store and retrieve attributes using the database """
        await database.start()
        # Push a bunch of attributes
        for idx in range(100):
            await database.push(Attribute(name=f"attr_{idx}", value=f"value_{idx}"))
        # Get attributes
        attrs = await database.get(Attribute, value=Query(like="value_1%"))
        assert len(attrs) == 11
        assert set(x.name for x in attrs) == {
            f"attr_{x}" for x in (1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)
        }
        assert set(x.value for x in attrs) == {
            f"value_{x}" for x in (1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)
        }
        # Clean-up
        await database.stop()

    async def test_log_entry(self, database):
        """ Store and retrieve log entries """
        await database.start()
        # Define transform
        database.define_transform(LogSeverity, "INTEGER", int, LogSeverity)
        # Push a bunch of logs
        for sev in LogSeverity:
            for idx in range(10):
                await database.push(LogEntry(severity=sev,
                                             message=f"{sev.name} - {idx}",
                                             timestamp=datetime.fromtimestamp(idx)))
        # Retrieve
        for sev in LogSeverity:
            entries = await database.get(LogEntry, severity=sev)
            assert len(entries) == 10
            assert set(x.severity for x in entries) == {sev}
            assert set(x.message for x in entries) == {f"{sev.name} - {x}" for x in range(10)}
            assert set(x.timestamp.timestamp() for x in entries) == set(range(10))
        # Clean-up
        await database.stop()

    async def test_proc_stat(self, database):
        """ Store and retrieve process statistics """
        await database.start()
        # Push a bunch of statistics
        for idx in range(100):
            await database.push(ProcStat(nproc    =(1 + idx),
                                         cpu      =20 * idx,
                                         mem      =100 * idx,
                                         vmem     =(100 * idx) + 25,
                                         timestamp=datetime.fromtimestamp(idx)))
        # Retrieve
        entries = await database.get(ProcStat, timestamp=Query(gte=datetime.fromtimestamp(90)))
        assert len(entries) == 10
        assert set(x.nproc for x in entries) == {(1 + x) for x in range(90, 100)}
        assert set(x.cpu for x in entries) == {(20 * x) for x in range(90, 100)}
        assert set(x.mem for x in entries) == {(100 * x) for x in range(90, 100)}
        assert set(x.vmem for x in entries) == {((100 * x) + 25) for x in range(90, 100)}
        assert set(x.timestamp.timestamp() for x in entries) == set(range(90, 100))
        # Clean-up
        await database.stop()
