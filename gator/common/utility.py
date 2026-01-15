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
import uuid
from typing import Awaitable, Callable, TypeVar, Union, overload

import expandvars


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
    ) -> Callable[_P, Awaitable[_R]]: ...
except ImportError:

    @overload
    def as_couroutine(
        fn: Callable[..., Union[_R, Awaitable[_R]]],
    ) -> Callable[..., Awaitable[_R]]: ...


def as_couroutine(fn):
    "Coerces a function into a couroutine"

    if asyncio.iscoroutinefunction(fn):
        return fn

    @functools.wraps(fn)
    async def async_fn(*args, **kwargs):
        return fn(*args, **kwargs)

    return async_fn


def find_command_substitutions(text: str) -> list[tuple[int, int, str]]:
    """
    Find all command substitutions $(cmd) and `cmd` in the text, handling
    nested parentheses correctly.

    Returns a list of (start_pos, end_pos, original_text) tuples.
    """
    substitutions = []
    i = 0

    while i < len(text):
        # Check for $(
        if i < len(text) - 1 and text[i : i + 2] == "$(":
            start = i
            i += 2
            depth = 1

            # Find matching closing parenthesis
            while i < len(text) and depth > 0:
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                i += 1

            if depth == 0:
                # Found matching closing paren
                substitutions.append((start, i, text[start:i]))
            # else: unmatched - let it through and shell will error

        # Check for backticks
        elif text[i] == "`":
            start = i
            i += 1

            # Find closing backtick (no nesting for backticks)
            while i < len(text) and text[i] != "`":
                # Handle escaped backticks
                if text[i] == "\\" and i + 1 < len(text):
                    i += 2
                else:
                    i += 1

            if i < len(text) and text[i] == "`":
                i += 1
                substitutions.append((start, i, text[start:i]))
            # else: unmatched - let it through
        else:
            i += 1

    return substitutions


def expand_vars_preserve_commands(text: str, environ: dict) -> str:
    """
    Expand environment variables using expandvars, but preserve command
    substitution syntax ($(cmd) and `cmd`) for the shell to handle later.

    This prevents issues where expandvars would strip the $ from $(cmd),
    turning it into (cmd) which is a syntax error.

    Uses a placeholder approach:
    1. Find and replace command substitutions with unique placeholders
    2. Run expandvars on the text
    3. Restore the command substitutions
    """
    # Find all command substitutions (handles nested parentheses)
    substitutions = find_command_substitutions(text)

    if not substitutions:
        # No command substitutions, just expand normally
        return expandvars.expand(text, environ=environ)

    # Generate a unique prefix for placeholders to avoid collisions
    unique_id = uuid.uuid4().hex[:8]

    # Replace with placeholders in reverse order to maintain positions
    placeholders = {}
    result = text

    for idx, (start, end, original) in enumerate(reversed(substitutions)):
        placeholder = f"__GATOR_CMD_SUB_{unique_id}_{idx}__"
        placeholders[placeholder] = original
        result = result[:start] + placeholder + result[end:]

    # Expand variables with expandvars
    result = expandvars.expand(result, environ=environ)

    # Restore command substitutions
    for placeholder, original in placeholders.items():
        result = result.replace(placeholder, original)

    return result
