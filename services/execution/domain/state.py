from __future__ import annotations

from enum import Enum


class ExecutionState(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    SUBMITTED = "SUBMITTED"

    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"

    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"

    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
