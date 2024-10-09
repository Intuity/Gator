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

from dataclasses import dataclass
from enum import IntEnum
from unittest.mock import AsyncMock, call

import pytest

from gator.common.db import Base, Database, Query


@pytest.fixture
def database(tmp_path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.mark.asyncio
class TestDatabase:
    async def test_register(self, database, mocker):
        """Register a dataclass with the database"""
        await database.start()
        # Setup a mock to capture SQLite queries
        sqlite = database._Database__db
        mocker.patch.object(sqlite, "_execute", new=AsyncMock())

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Register it
        await database.register(TestObj)
        # Check for the query
        sqlite._execute.assert_called_with(
            sqlite._conn.execute,
            "CREATE TABLE TestObj ("
            "db_uid INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key_a TEXT, "
            "key_b INTEGER)",
            [],
        )
        # Check push and get methods have been created
        assert database.push_testobj
        assert database.get_testobj
        # Check the dataclass has been registered
        assert TestObj in database.registered
        # Check the table is known
        assert "TestObj" in database.tables
        # Check that a second registration has no effect
        sqlite._execute.reset_mock()
        await database.register(TestObj)
        assert not sqlite._execute.called
        # Clean-up
        await database.stop()
        # Check a double stop doesn't cause problems
        await database.stop()

    async def test_push(self, database, mocker):
        """Push entries into the database"""
        await database.start()
        # Setup a mock to capture SQLite queries
        sqlite = database._Database__db
        mocker.patch.object(sqlite, "_execute", new=AsyncMock())

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Register it
        await database.register(TestObj)
        # Push entries
        await database.push(TestObj(key_a="hello", key_b=1234))
        await database.push(TestObj(key_a="goodbye", key_b=2345))
        # Check for queries
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "INSERT INTO TestObj (key_a, key_b) " "VALUES (?, ?)",
            ["hello", 1234],
        )
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "INSERT INTO TestObj (key_a, key_b) " "VALUES (?, ?)",
            ["goodbye", 2345],
        )
        # Clean-up
        await database.stop()

    async def test_push_uids(self, database):
        """Push entries into the database and check a unique ID is assigned each time"""
        await database.start()

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Register it
        await database.register(TestObj)
        # Push entries
        entries = []
        for idx in range(100):
            await database.push(entry := TestObj(key_a=f"key_{idx}", key_b=idx))
            entries.append(entry)
        assert len({x.db_uid for x in entries}) == 100
        # Clean-up
        await database.stop()

    async def test_push_callback(self, database):
        """Check callback executed for each push"""
        await database.start()

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Register it
        push_cb = AsyncMock()
        await database.register(TestObj, push_callback=push_cb)
        # Push entries
        entries = []
        for idx in range(100):
            await database.push(entry := TestObj(key_a=f"key_{idx}", key_b=idx))
            entries.append(entry)
        # Check for calls
        push_cb.assert_has_calls([call(x) for x in entries])
        # Clean-up
        await database.stop()

    async def test_get(self, database, mocker):
        """Push entries into the database"""
        await database.start()
        # Setup a mock to capture SQLite queries
        sqlite = database._Database__db
        mocker.patch.object(sqlite, "_execute", new=AsyncMock())

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Register it
        await database.register(TestObj)
        # Perform a simple query
        await database.get(TestObj)
        sqlite._execute.assert_any_call(sqlite._conn.execute, "SELECT * FROM TestObj", {})
        sqlite._execute.reset_mock()
        # Perform a count query
        await database.get(TestObj, sql_count=True)
        sqlite._execute.assert_any_call(
            sqlite._conn.execute, "SELECT COUNT(db_uid) FROM TestObj", {}
        )
        sqlite._execute.reset_mock()
        # Perform a limited query
        await database.get(TestObj, sql_limit=30)
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj LIMIT :limit",
            {"limit": 30},
        )
        sqlite._execute.reset_mock()
        # Perform a ordered query
        await database.get(TestObj, sql_order_by=("key_b", False))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj ORDER BY key_b DESC",
            {},
        )
        sqlite._execute.reset_mock()
        # Perform a basic filter query
        await database.get(TestObj, key_a="hello")
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_a = :match_key_a",
            {"match_key_a": "hello"},
        )
        sqlite._execute.reset_mock()
        # Perform a ranged (X >= 10) filter query
        await database.get(TestObj, key_b=Query(gte=10))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_b >= :gte_key_b",
            {"gte_key_b": 10},
        )
        sqlite._execute.reset_mock()
        # Perform a ranged (X < 20) filter query
        await database.get(TestObj, key_b=Query(lt=20))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_b < :lt_key_b",
            {"lt_key_b": 20},
        )
        sqlite._execute.reset_mock()
        # Perform a ranged (X >= 10 & X < 20) filter query
        await database.get(TestObj, key_b=Query(gte=10, lt=20))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_b >= :gte_key_b AND key_b < :lt_key_b",
            {"gte_key_b": 10, "lt_key_b": 20},
        )
        sqlite._execute.reset_mock()
        # Perform a ranged (X = 10 & X <= 20) filter query
        await database.get(TestObj, key_b=Query(gt=10, lte=20))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_b > :gt_key_b AND key_b <= :lte_key_b",
            {"gt_key_b": 10, "lte_key_b": 20},
        )
        sqlite._execute.reset_mock()
        # Perform a exact filter query
        await database.get(TestObj, key_b=Query(exact=15))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_b = :exact_key_b",
            {"exact_key_b": 15},
        )
        sqlite._execute.reset_mock()
        # Perform a loose filter query
        await database.get(TestObj, key_a=Query(like="test%"))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "SELECT * FROM TestObj WHERE key_a LIKE :like_key_a",
            {"like_key_a": "test%"},
        )
        sqlite._execute.reset_mock()
        # Clean-up
        await database.stop()

    async def test_db_update(self, database, mocker):
        """Check that the update function modifies the database"""
        await database.start()
        # Setup a mock to capture SQLite queries
        sqlite = database._Database__db
        mocker.patch.object(sqlite, "_execute", new=AsyncMock())

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Update an object
        await database.update(TestObj(db_uid=123))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "UPDATE TestObj SET key_a = :key_a, " "key_b = :key_b WHERE db_uid = :db_uid",
            {"db_uid": 123, "key_a": "", "key_b": 0},
        )
        # Update an object with values
        await database.update(TestObj(db_uid=123, key_a="hello", key_b=234))
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "UPDATE TestObj SET key_a = :key_a, " "key_b = :key_b WHERE db_uid = :db_uid",
            {"db_uid": 123, "key_a": "hello", "key_b": 234},
        )
        # Clean-up
        await database.stop()

    async def test_push_and_get(self, database):
        """Push entries into the database and check a unique ID is assigned each time"""
        await database.start()

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Push entries (without prior registration)
        entries = []
        for idx in range(100):
            await database.push(entry := TestObj(key_a=f"key_{idx}", key_b=idx))
            entries.append(entry)
        assert len({x.db_uid for x in entries}) == 100
        # Retrieve entries
        entries = await database.get(TestObj)
        assert len(entries) == 100
        assert {x.key_a for x in entries} == {f"key_{x}" for x in range(100)}
        # Retrieve count
        count = await database.get(TestObj, sql_count=True)
        assert count == 100
        # Apply filter
        count = await database.get(TestObj, sql_count=True, key_b=Query(gte=10, lt=20))
        assert count == 10
        # Clean-up
        await database.stop()

    async def test_reload(self, tmp_path):
        """Check that tables can be reloaded from disk"""

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: int = 0

        # Common database path
        sqlite_path = tmp_path / "test.sqlite"
        # Create an original database and pump in some entries
        db_a = Database(sqlite_path)
        await db_a.start()
        for idx in range(100):
            await db_a.push(TestObj(key_a=f"key_{idx}", key_b=idx))
        entries = await db_a.get(TestObj)
        assert len(entries) == 100
        await db_a.stop()
        # Reload
        db_b = Database(sqlite_path)
        await db_b.start()
        assert "TestObj" in db_b.tables
        assert TestObj not in db_b.registered
        entries = await db_b.get(TestObj)
        assert len(entries) == 100
        assert {x.key_a for x in entries} == {f"key_{x}" for x in range(100)}
        assert {x.key_b for x in entries} == set(range(100))
        await db_b.stop()

    async def test_custom_transform(self, database, mocker):
        """Register a custom transformation"""
        await database.start()
        # Setup a mock to capture SQLite queries
        sqlite = database._Database__db
        mocker.patch.object(sqlite, "_execute", new=AsyncMock())

        # Define an enumeration and it's transform
        class TestEnum(IntEnum):
            ORANGE = 0
            APPLE = 1
            BANANA = 2

        database.define_transform(
            TestEnum,
            sql_type="INTEGER",
            transform_put=lambda x: int(x),
            transform_get=lambda x: TestEnum(x),
        )

        # Define a dataclass
        @dataclass
        class TestObj(Base):
            key_a: str = ""
            key_b: TestEnum = TestEnum.ORANGE

        # Register it
        await database.register(TestObj)
        sqlite._execute.assert_called_with(
            sqlite._conn.execute,
            "CREATE TABLE TestObj ("
            "db_uid INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key_a TEXT, "
            "key_b INTEGER)",
            [],
        )
        sqlite._execute.reset_mock()
        # Push entries
        await database.push(TestObj(key_a="hello", key_b=TestEnum.APPLE))
        await database.push(TestObj(key_a="goodbye", key_b=TestEnum.BANANA))
        # Check for queries
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "INSERT INTO TestObj (key_a, key_b) " "VALUES (?, ?)",
            ["hello", 1],
        )
        sqlite._execute.assert_any_call(
            sqlite._conn.execute,
            "INSERT INTO TestObj (key_a, key_b) " "VALUES (?, ?)",
            ["goodbye", 2],
        )
        # Clean-up
        await database.stop()

    def test_dataclass_serialize(self):
        """Use the serialize/deserialize functions of the base dataclass"""

        # Define a dataclass which inherits from the DB's base class
        @dataclass
        class Demo(Base):
            name: str = ""
            value: int = 0
            switch: bool = False

        # List fields
        assert {x.name for x in Demo.list_fields()} == {
            "name",
            "value",
            "switch",
        }
        # Create an object
        obj = Demo(db_uid=123, name="fred", value=2, switch=True)
        # Serialize an instance
        srlz = obj.serialize()
        assert set(srlz.keys()) == {"name", "value", "switch"}
        assert srlz["name"] == "fred"
        assert srlz["value"] == 2
        assert srlz["switch"] is True
        # Deserialize
        inst = Demo.deserialize(srlz)
        assert inst.name == "fred"
        assert inst.value == 2
        assert inst.switch is True
        # Serialize to a list
        l_srlz = obj.serialize(as_list=True)
        assert l_srlz == ["fred", 2, True]
        # Deserialize
        inst = Demo.deserialize(l_srlz)
        assert inst.name == "fred"
        assert inst.value == 2
        assert inst.switch is True
        # Omit a value
        o_srlz = obj.serialize(omit=["value"])
        assert o_srlz == {"name": "fred", "switch": True}
        ol_srlz = obj.serialize(as_list=True, omit=["value"])
        assert ol_srlz == ["fred", True]
        # Deserialize from omitted versions
        inst = Demo.deserialize(o_srlz, omit=["value"])
        assert inst.name == "fred"
        assert inst.value == 0
        assert inst.switch is True
        inst = Demo.deserialize(ol_srlz, omit=["value"])
        assert inst.name == "fred"
        assert inst.value == 0
        assert inst.switch is True
