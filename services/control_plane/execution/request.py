"""
ExecutionControlRequest — the atomic unit evaluated by Execution Control
(Commit 26 Part 1.4, spec section 25).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionAction(str, Enum):

    NEW_ORDER = "NEW_ORDER"

    CANCEL_ORDER = "CANCEL_ORDER"

    REDUCE_ORDER = "REDUCE_ORDER"

    EMERGENCY_FLATTEN = "EMERGENCY_FLATTEN"


@dataclass(frozen=True)
class ExecutionControlRequest:

    execution_id: str

    venue: str

    action: str

    emergency: bool = False

    reduce_only: bool = False
