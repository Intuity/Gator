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
import atexit
import dataclasses
import functools
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import aiosqlite


@dataclasses.dataclass
class Base:
    db_uid : Optional[int] = None

    @classmethod
    @functools.lru_cache
    def list_fields(cls) -> List[dataclasses.field]:
        return [f for f in dataclasses.fields(cls) if f.name != "db_uid"]

    def serialize(self,
                  as_list : bool = False,
                  omit    : Optional[List[str]] = None) -> Dict[str, int]:
        omit = omit or []
        if as_list:
            return [getattr(self, f.name) for f in self.list_fields() if f.name not in omit]
        else:
            return { f.name: getattr(self, f.name) for f in self.list_fields() if f.name not in omit }

    @classmethod
    def deserialize(cls,
                    values : Union[Dict[str, int], List[int]],
                    omit   : Optional[List[str]] = None) -> "Base":
        inst = cls()
        omit = omit or []
        if isinstance(values, list):
            fields = [x for x in cls.list_fields() if x.name not in omit]
            omit   = omit or []
            for key, value in zip(fields, values):
                setattr(inst, key.name, value)
        else:
            fnames = [x.name for x in inst.list_fields()]
            for key, value in values.items():
                if key in fnames:
                    setattr(inst, key, value)
        return inst


@dataclasses.dataclass
class Query:
    """
    The query object supports more complex SQLite queries than just a direct
    match. For example 'Query(gte=123, lt=234)' when provided to a 'get_X'
    method of the Database object will construct this query:
    $> SELECT * FROM X WHERE attr >= :gte AND attr < :lt
    """
    exact : Optional[Any] = None
    like  : Optional[str] = None
    gt    : Optional[int] = None
    gte   : Optional[int] = None
    lt    : Optional[int] = None
    lte   : Optional[int] = None


class DatabaseError(Exception):
    pass


class Database:
    """
    Light-weight wrapper around SQLite3 which serialises and deserialises
    dataclass objects. When dataclasses are registered, this automatically
    creates a matching table in the database and sets up 'push_X' and 'get_X'
    functions to allow data to be submitted to and queried from the table.
    """

    def __init__(self, path : Path) -> None:
        self.path = path
        # Ensure path's parent folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Track which dataclasses are register
        self.registered = []
        self.tables = []
        # Placeholder for the database instance
        self.__db = None
        # Record transforms
        self.__transforms = {}
        self.define_transform(int, "INTEGER")
        self.define_transform(datetime,
                              "INTEGER",
                              lambda x: x.timestamp(),
                              datetime.fromtimestamp)

    async def start(self) -> None:
        self.__db = await aiosqlite.connect(self.path.as_posix(), timeout=1)
        def _teardown() -> None:
            asyncio.run(self.stop())
        atexit.register(_teardown)
        async with self.__db.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cursor:
            result = await cursor.fetchall()
            self.tables = [x[0] for x in result]

    async def stop(self) -> None:
        if self.__db is not None:
            await self.__db.commit()
            await self.__db.close()
        self.__db = None

    def define_transform(self,
                         obj_type : Any,
                         sql_type : str = "TEXT",
                         transform_put : Optional[Callable] = None,
                         transform_get : Optional[Callable] = None) -> None:
        """
        Define a custom transformation from a Python object to an SQL type and
        vice-versa.

        :param obj_type:      The Python object type
        :param sql_type:      The SQLite column type
        :param transform_put: Optional transform from the Python type into the
                              SQLite type
        :param transform_get: Optional transform from the SQLite type into the
                              Python type
        """
        self.__transforms[obj_type] = (
            sql_type,
            transform_put or (lambda x: x),
            transform_get or (lambda x: x)
        )

    def get_transform(self, obj_type : Any) -> Tuple[str, Callable, Callable]:
        """
        Lookup a transform for a given object type, returning the SQLite
        column type and the transforming functions to and from the SQLite type.

        :param obj_type: The Python object type
        :returns:        Tuple of the SQLite type, transformation function from
                         Python to SQLite, and the reverse
        """
        return self.__transforms.get(obj_type, ("TEXT", lambda x: x, lambda x: x))

    def transform_to_sql(self, obj : Any) -> Any:
        """
        Use registered transformations to convert a Python object to it's SQLite
        equivalent.

        :param obj: Object to convert
        :returns:   Translated value
        """
        _, to_func, _ = self.get_transform(type(obj))
        return to_func(obj)

    async def register(self,
                       descr : Type[dataclasses.dataclass],
                       push_callback : Optional[Callable] = None) -> None:
        """
        Register a dataclass - this will create a matching table in the database
        and setup the required 'push_X' and 'get_X' methods.

        :param descr:         The dataclass to register
        :param push_callback: Method to call whenever data is pushed into a
                              table in the database
        """
        # Create the table in the database and collect transformations to/from SQL
        if descr.__name__ not in self.tables:
            fields = []
            for field in descr.list_fields():
                stype, _, _ = self.get_transform(field.type)
                fields.append(f"{field.name} {stype}")
            query = (
                f"CREATE TABLE {descr.__name__} ("
                f"db_uid INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(fields)})"
            )
            await self.__db.execute(query)
            self.tables.append(descr.__name__)
        # Setup push/get methods
        if descr not in self.registered:
            fnames = []
            transforms_put = []
            transforms_get = []
            for field in descr.list_fields():
                fnames.append(field.name)
                _, tput, tget = self.get_transform(field.type)
                transforms_put.append(tput)
                transforms_get.append(tget)
            # Create a 'push' method
            sql_put = (
                f"INSERT INTO {descr.__name__} ({', '.join(fnames)}) "
                f"VALUES ({', '.join(['?' for _ in fnames])})"
            )
            async def _push(object : descr) -> None:
                nonlocal sql_put, transforms_put
                assert isinstance(object, descr), "Wrong object type"
                values = [x(y) for x, y in zip(transforms_put, dataclasses.astuple(object)[1:])]
                async with self.__db.execute(sql_put, values) as cursor:
                    object.db_uid = cursor.lastrowid
                if push_callback is not None:
                    await push_callback(object)
                return object.db_uid
            setattr(self, f"push_{descr.__name__.lower()}", _push)
            # Create an 'update' method
            sql_update = (
                f"UPDATE {descr.__name__} SET " +
                ", ".join(f"{f} = :{f}" for f in fnames) +
                " WHERE db_uid = :db_uid"
            )
            async def _update(object : descr) -> None:
                nonlocal sql_update, transforms_put
                assert isinstance(object, descr), "Wrong object type"
                assert object.db_uid is not None, "Object has no UID field"
                params = {k: x(y) for k, x, y in zip(fnames, transforms_put, dataclasses.astuple(object)[1:])}
                params["db_uid"] = object.db_uid
                await self.__db.execute(sql_update, params)
            setattr(self, f"update_{descr.__name__.lower()}", _update)
            # Create a 'getter' method
            sql_base_query = f"SELECT * FROM {descr.__name__}"
            sql_base_count = f"SELECT COUNT(db_uid) FROM {descr.__name__}"
            async def _get(sql_order_by : Optional[Tuple[str, bool]] = None,
                           sql_count    : bool = False,
                           sql_limit    : Optional[int] = None,
                           **kwargs     : Dict[str, Union[Query, str, int]]) -> List[descr]:
                nonlocal sql_base_query, sql_base_count, transforms_get
                query_str = [sql_base_query, sql_base_count][sql_count]
                conditions = []
                parameters = {}
                for key, val in kwargs.items():
                    if isinstance(val, Query):
                        if val.exact is not None:
                            conditions.append(f"{key} = :exact_{key}")
                            parameters[f"exact_{key}"] = self.transform_to_sql(val.exact)
                        elif val.like is not None:
                            conditions.append(f"{key} LIKE :like_{key}")
                            parameters[f"like_{key}"] = self.transform_to_sql(val.like)
                        else:
                            # Greater than (or equal to)
                            if val.gt is not None:
                                conditions.append(f"{key} > :gt_{key}")
                                parameters[f"gt_{key}"] = self.transform_to_sql(val.gt)
                            elif val.gte is not None:
                                conditions.append(f"{key} >= :gte_{key}")
                                parameters[f"gte_{key}"] = self.transform_to_sql(val.gte)
                            # Less than (or equal to)
                            if val.lt is not None:
                                conditions.append(f"{key} < :lt_{key}")
                                parameters[f"lt_{key}"] = self.transform_to_sql(val.lt)
                            elif val.lte is not None:
                                conditions.append(f"{key} <= :lte_{key}")
                                parameters[f"lte_{key}"] = self.transform_to_sql(val.lte)
                    else:
                        conditions.append(f"{key} = :match_{key}")
                        parameters[f"match_{key}"] = self.transform_to_sql(val)
                if conditions:
                    query_str += " WHERE " + " AND ".join(conditions)
                if sql_order_by:
                    column, ascending = sql_order_by
                    query_str += f" ORDER BY {column} {['DESC', 'ASC'][ascending]}"
                if sql_limit is not None:
                    query_str += " LIMIT :limit"
                    parameters["limit"] = sql_limit
                async with self.__db.execute(query_str, parameters) as cursor:
                    if sql_count:
                        data = await cursor.fetchone()
                    else:
                        data = await cursor.fetchall()
                if sql_count:
                    return data[0]
                else:
                    objects = []
                    for db_uid, *raw_vals in data:
                        mapped = {n: y(z) for n, y, z in zip(fnames, transforms_get, raw_vals)}
                        objects.append(descr(**mapped, db_uid=db_uid))
                    return objects
            setattr(self, f"get_{descr.__name__.lower()}", _get)
            # Track registration
            self.registered.append(descr)

    async def push(self, object : Any) -> None:
        descr = type(object)
        if descr not in self.registered:
            await self.register(descr)
        result = await getattr(self, f"push_{descr.__name__.lower()}")(object)
        return result

    async def update(self, object : Any) -> None:
        descr = type(object)
        if descr not in self.registered:
            await self.register(descr)
        result = await getattr(self, f"update_{descr.__name__.lower()}")(object)
        return result

    async def get(self,
            descr : Type[dataclasses.dataclass],
            **kwargs : Dict[str, Any]) -> Any:
        if descr not in self.registered:
            await self.register(descr)
        result = await getattr(self, f"get_{descr.__name__.lower()}")(**kwargs)
        return result
