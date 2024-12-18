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
import functools
import os
import pwd
from typing import Awaitable, Callable, TypeVar, Union, overload


@functools.lru_cache
def get_username() -> str:
    return pwd.getpwuid(os.getuid())[0]


_R = TypeVar("_R")
try:
    # 3.8 doesn't support ParamSpec
    from typing import ParamSpec

    _P = ParamSpec("_P")

    @overload
    def as_couroutine(
        fn: Callable[_P, Union[_R, Awaitable[_R]]],
    ) -> Callable[_P, Awaitable[_R]]:
        ...
except ImportError:

    @overload
    def as_couroutine(
        fn: Callable[..., Union[_R, Awaitable[_R]]],
    ) -> Callable[..., Awaitable[_R]]:
        ...


def as_couroutine(fn):
    "Coerces a function into a couroutine"

    if asyncio.iscoroutinefunction(fn):
        return fn

    @functools.wraps(fn)
    async def async_fn(*args, **kwargs):
        return fn(*args, **kwargs)

    return async_fn
