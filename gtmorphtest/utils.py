#!/usr/bin/env python3
"""Support functions and classes for MorphTest."""

import shutil
from collections import OrderedDict
from typing import Any, Mapping


def string_to_list(data: bytes | str | list[str]) -> list[str]:
    """Normalise a scalar or sequence into a list of strings.

    Args:
        data: Bytes, a string, or an already-iterable value.

    Returns:
        A single-item list for bytes (decoded as UTF-8) or str input;
        otherwise `data` unchanged.
    """
    if isinstance(data, bytes):
        return [data.decode("utf-8")]
    elif isinstance(data, str):
        return [data]
    else:
        return data


def invert_dict(
    data: Mapping[str, str | list[str]],
) -> OrderedDict[str, list[str]]:
    """Invert a mapping, grouping the original keys under each value.

    Args:
        data: Mapping of key to a value or list of values.

    Returns:
        An OrderedDict mapping each value to the list of keys that
        pointed at it, in first-seen order.
    """
    tmp: OrderedDict[str, list[str]] = OrderedDict()
    for key, val in data.items():
        for v in string_to_list(val):
            d = tmp.setdefault(v, [])
            if key not in d:
                d.append(key)
    return tmp


COLORS: dict[str, str] = {
    "red": "\033[1;31m",
    "green": "\033[0;32m",
    "orange": "\033[0;33m",
    "yellow": "\033[1;33m",
    "blue": "\033[0;34m",
    "light_blue": "\033[0;36m",
    "reset": "\033[m"
}


def colourise(string: str, *args: Any, **kwargs: Any) -> str:
    """Format a string, exposing the ANSI colour codes as named fields.

    Args:
        string: A `str.format` template.
        *args: Positional arguments passed to `str.format`.
        **kwargs: Extra named fields; overridden by the colour names.

    Returns:
        The formatted string.
    """
    kwargs.update(COLORS)
    return string.format(*args, **kwargs)


def check_path_exists(program: str) -> str:
    """Locate an executable on $PATH.

    Args:
        program: Name of the executable to look for.

    Returns:
        The full path to the executable.

    Raises:
        EnvironmentError: If the program is not on $PATH.
    """
    out = shutil.which(program)
    if out is None:
        raise EnvironmentError(f"Cannot find `{program}`. Check $PATH.")
    return out


class LookupToolError(Exception):
    """Raised when the external lookup tool exits with an error."""


if __name__ == "__main__":
    pass
