"""Execution response (Commit 33 Part 1.3).

An :class:`ExecutionResponse` is the venue/gateway's answer to an execution
request.  ``UNKNOWN`` is a first-class state: a network timeout does not mean
the order failed - the order keeps its current state and must be queried /
reconciled before any retry (Commit 33 Part 1.3 #7-#8, #22-#23).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExecutionResponseStatus(str, Enum):
    """Gateway's knowledge about the execution result."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExecutionResponse:
    """Answer to an execution request."""

    execution_request_id: str
    order_id: str
    status: ExecutionResponseStatus
    venue_order_id: Optional[str]
    reject_reason: Optional[str]
    timestamp: datetime
    correlation_id: str
