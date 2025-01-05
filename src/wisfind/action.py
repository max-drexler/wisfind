"""wisfind.action

Actions that can be performed on WIS2 messages.
"""

from __future__ import annotations

import functools
import json
from typing import Callable

from wisfind.definitions import WNM

# An action, accepts either a structured WNM or the direct dictionary
ActionFuncType = Callable[[WNM | dict], None]

# A function that initializes an action
ActionInitType = Callable[[...], ActionFuncType]


def emit_json(end="\n", indent: int | None=None) -> ActionFuncType:
    """Initialize an action that prints messages to stdout as JSON string.

    Args:
        end (str): String to print after each message's JSON. Default is '\n'.
        indent (int | None): How many spaces to indent each key in the JSON output.
        Default is None.

    Returns:
        ActionFuncType: A function that prints each message to stdout as a JSON string.
    """

    def emit(msg: WNM | dict) -> None:
        """Prints the WNM to stdout as a JSON string."""
        data = msg.model_dump_json(indent=indent) if isinstance(msg, WNM) else json.dumps(msg, indent=indent)
        print(data, end=end)

    return emit


def emit_fjson(format_str: str) -> ActionFuncType:
    pass


