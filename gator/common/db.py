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

import atexit
import dataclasses
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from threading import Lock

try:
    import uwsgi
except ImportError:
    uwsgi = None


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

    # Collect transformations for types to store into the database
    TRANSFORMS = {
        int     : ("INTEGER", lambda x: x, lambda x: x),
        datetime: ("INTEGER",
                   lambda x: x.timestamp(),
                   lambda x: datetime.fromtimestamp(x))
    }

    def __init__(self,
                 path : Path,
                 uwsgi : bool = False) -> None:
        self.path = path
        self.uwsgi = uwsgi
        # Ensure path's parent folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create a instance for the SQLite database
        kwargs = {}
        if self.uwsgi:
            kwargs["isolation_level"] = None
        self.__db = sqlite3.connect(self.path.as_posix(),
                                    timeout=1,
                                    check_same_thread=False,
                                    **kwargs)
        atexit.register(self.__close)
        # Create a lock for using the DB
        self.__db_lock = Lock()
        # Track which dataclasses are register
        self.registered = []
        self.tables = []
        # Lookup existing registrations
        with closing(self.__db.cursor()) as cursor:
            query = "SELECT name FROM sqlite_master WHERE type = 'table'"
            self.tables = [x[0] for x in cursor.execute(query).fetchall()]

    def __close(self):
        if self.uwsgi:
            uwsgi.lock(0)
        self.__db_lock.acquire()
        self.__db.commit()
        self.__db.close()
        self.__db_lock.release()
        if self.uwsgi:
            uwsgi.unlock(0)

    @classmethod
    def define_transform(cls,
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
        cls.TRANSFORMS[obj_type] = (
            sql_type,
            transform_put or (lambda x: x),
            transform_get or (lambda x: x)
        )

    def register(self,
                 descr : Type[dataclasses.dataclass],
                 push_callback : Optional[Callable] = None) -> None:
        """
        Register a dataclass - this will create a matching table in the database
        and setup the required 'push_X' and 'get_X' methods.

        :param descr:         The dataclass to register
        :param push_callback: Method to call whenever data is pushed into a
                              table in the database
        """
        # Lock the database to prevent other mutations
        self.__db_lock.acquire()
        # Create the table in the database and collect transformations to/from SQL
        if descr.__name__ not in self.tables:
            fields = []
            for field in dataclasses.fields(descr):
                stype, _, _ = self.TRANSFORMS.get(field.type, ("TEXT", None, None))
                fields.append(f"{field.name} {stype}")
            with closing(self.__db.cursor()) as cursor:
                cursor.execute(
                    f"CREATE TABLE {descr.__name__} ("
                    f"db_uid INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(fields)})"
                )
            self.tables.append(descr.__name__)
        # Setup push/get methods
        if descr not in self.registered:
            fnames = [x.name for x in dataclasses.fields(descr)]
            transforms_put = []
            transforms_get = []
            for field in dataclasses.fields(descr):
                _, tput, tget = self.TRANSFORMS.get(field.type, (None, lambda x: x, lambda x: x))
                transforms_put.append(tput)
                transforms_get.append(tget)
            # Create a 'push' method
            sql_put = (
                f"INSERT INTO {descr.__name__} ({', '.join(fnames)}) "
                f"VALUES ({', '.join(['?' for _ in fnames])})"
            )
            def _push(object : descr) -> None:
                nonlocal sql_put, transforms_put
                assert isinstance(object, descr)
                self.__db_lock.acquire()
                with closing(self.__db.cursor()) as cursor:
                    cursor.execute(sql_put, [x(y) for x, y in zip(transforms_put, dataclasses.astuple(object))])
                self.__db_lock.release()
                if push_callback is not None:
                    push_callback(object)
            setattr(self, f"push_{descr.__name__.lower()}", _push)
            # Create a 'getter' method
            sql_base_query = f"SELECT * FROM {descr.__name__}"
            sql_base_count = f"SELECT COUNT(db_uid) FROM {descr.__name__}"
            def _get(sql_order_by : Optional[Tuple[str, bool]] = None,
                    sql_count    : bool = False,
                    **kwargs : Dict[str, Union[Query, str, int]]) -> List[descr]:
                nonlocal sql_base_query, sql_base_count, transforms_get
                query_str = [sql_base_query, sql_base_count][sql_count]
                conditions = []
                parameters = {}
                for key, val in kwargs.items():
                    if isinstance(val, Query):
                        if val.exact is not None:
                            conditions.append(f"{key} = :exact_{key}")
                            parameters[f"exact_{key}"] = val.exact
                        elif val.like is not None:
                            conditions.append(f"{key} LIKE :like_{key}")
                            parameters[f"like_{key}"] = val.like
                        else:
                            # Greater than (or equal to)
                            if val.gt is not None:
                                conditions.append(f"{key} > :gt_{key}")
                                parameters[f"gt_{key}"] = val.gt
                            elif val.gte is not None:
                                conditions.append(f"{key} >= :gte_{key}")
                                parameters[f"gte_{key}"] = val.gte
                            # Less than (or equal to)
                            if val.lt is not None:
                                conditions.append(f"{key} < :lt_{key}")
                                parameters[f"lt_{key}"] = val.lt
                            elif val.lte is not None:
                                conditions.append(f"{key} <= :lte_{key}")
                                parameters[f"lte_{key}"] = val.lte
                    else:
                        conditions.append(f"{key} = :match_{key}")
                        parameters[f"match_{key}"] = val
                if kwargs:
                    query_str += " WHERE " + " AND ".join(conditions)
                if sql_order_by:
                    column, ascending = sql_order_by
                    query_str += f" ORDER BY {column} {['DESC', 'ASC'][ascending]}"
                self.__db_lock.acquire()
                with closing(self.__db.cursor()) as cursor:
                    data = list(cursor.execute(query_str, parameters).fetchall())
                self.__db_lock.release()
                if sql_count:
                    return data[0][0]
                else:
                    # NOTE: The [1:] is to skip the UID column
                    return [descr(*[y(z) for y, z in zip(transforms_get, x[1:])]) for x in data]
            setattr(self, f"get_{descr.__name__.lower()}", _get)
            # Track registration
            self.registered.append(descr)
        # Release lock
        self.__db_lock.release()

    def push(self, object : Any) -> None:
        descr = type(object)
        if descr not in self.registered:
            self.register(descr)
        getattr(self, f"push_{descr.__name__.lower()}")(object)

    def get(self,
            descr : Type[dataclasses.dataclass],
            **kwargs : Dict[str, Any]) -> Any:
        if descr not in self.registered:
            self.register(descr)
        return getattr(self, f"get_{descr.__name__.lower()}")(**kwargs)
