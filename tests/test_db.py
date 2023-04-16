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
from tempfile import TemporaryDirectory
from datetime import datetime

from gator.db import Attribute, Database, ProcStat

class TestDatabase:

    def setup_method(self):
        self.tmp = TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")

    def teardown_method(self):
        self.db.stop()
        self.tmp.cleanup()

    def test_attributes(self):
        """ Store and retrieve attributes """
        # Push some attributes
        for idx in range(20):
            attr = Attribute(f"attr_{idx}", f"value_{idx}")
            self.db.push_attribute(attr)
        # Retrieve all attributes
        attrs = self.db.get_attributes()
        assert len(attrs) == 20
        for idx, attr in enumerate(attrs):
            assert attr.name == f"attr_{idx}"
            assert attr.value == f"value_{idx}"
        # Retrieve all attributes starting with 'attr_1'
        attrs = self.db.get_attributes("attr_1%")
        assert len(attrs) == 11
        assert attrs[0] == ("attr_1", "value_1")
        for idx, attr in enumerate(attrs[1:]):
            assert attr == (f"attr_{idx+10}", f"value_{idx+10}")

    def test_logging(self):
        """ Log and retrieve messages """
        # Push some messages
        for idx in range(10):
            self.db.push_log("debug", "Testing logging at debug", idx)
            self.db.push_log("info", "Testing logging at info", idx)
            self.db.push_log("warning", "Testing logging at warning", idx)
            self.db.push_log("error", "Testing logging at error", idx)
        # Retrieve all messages
        msgs = self.db.get_logs()
        assert len(msgs) == 40
        assert { x.severity for x in msgs } == { "DEBUG", "INFO", "WARNING", "ERROR" }
        assert { x.time for x in msgs } == set(range(10))
        # Retrieve just INFO messages
        msgs = self.db.get_logs(severity="INFO", exact_severity=True)
        assert len(msgs) == 10
        assert { x.severity for x in msgs } == { "INFO" }
        assert { x.time for x in msgs } == set(range(10))
        # Retrieve WARNING and ERROR messages
        msgs = self.db.get_logs(severity="WARNING")
        assert len(msgs) == 20
        assert { x.severity for x in msgs } == { "WARNING", "ERROR" }
        assert { x.time for x in msgs } == set(range(10))
        # Retrieve messages between time 5 & 8 (includes 5, 6, and 7)
        msgs = self.db.get_logs(after=5, before=8)
        assert len(msgs) == 12
        assert { x.severity for x in msgs } == { "DEBUG", "INFO", "WARNING", "ERROR" }
        assert { x.time for x in msgs } == { 5, 6, 7 }
        # Retrieve messages with a string filter
        msgs = self.db.get_logs(message=r"%warning")
        assert len(msgs) == 10
        assert { x.severity for x in msgs } == { "WARNING" }
        assert { x.time for x in msgs } == set(range(10))
        # Retrieve messages with all filters
        msgs = self.db.get_logs(severity="INFO",
                                message =r"%error",
                                after   =5,
                                before  =8)
        assert len(msgs) == 3
        assert { x.severity for x in msgs } == { "ERROR" }
        assert { x.time for x in msgs } == { 5, 6, 7 }

    def test_statistics(self):
        """ Push and retrieve process statistics """
        # Push simple statistics
        for idx in range(100):
            self.db.push_statistics(ProcStat(datetime.fromtimestamp(idx),
                                             idx + 1,
                                             idx * 30,
                                             idx * 100,
                                             idx * 200))
        # Retrieve all statistics
        stats = self.db.get_statistics()
        assert len(stats) == 100
        assert [x.time  for x in stats] == [datetime.fromtimestamp(x) for x in range(100)]
        assert [x.nproc for x in stats] == [(x + 1  ) for x in range(100)]
        assert [x.cpu   for x in stats] == [(x * 30 ) for x in range(100)]
        assert [x.mem   for x in stats] == [(x * 100) for x in range(100)]
        assert [x.vmem  for x in stats] == [(x * 200) for x in range(100)]
        # Retrieve statistics in a window
        stats = self.db.get_statistics(after=20, before=30)
        assert len(stats) == 10
        assert [x.time  for x in stats] == [datetime.fromtimestamp(x) for x in range(20, 30)]
        assert [x.nproc for x in stats] == [(x + 1  ) for x in range(20, 30)]
        assert [x.cpu   for x in stats] == [(x * 30 ) for x in range(20, 30)]
        assert [x.mem   for x in stats] == [(x * 100) for x in range(20, 30)]
        assert [x.vmem  for x in stats] == [(x * 200) for x in range(20, 30)]
