"""Control command result (Commit 29 Part 1.1 §16).

Example::

    command_id:   CMD-001
    state:        SUCCEEDED
    success:      true
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import ControlState


@dataclass(frozen=True)
class ControlResult:
    command_id: str
    state: str = ControlState.SUCCEEDED.value
    success: bool = True
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None
