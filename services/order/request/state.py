"""Order request lifecycle states.

The state answers *"where is this request right now?"*.  It is the current
snapshot of the aggregate; the transition history (see :mod:`lifecycle`)
records *"why did it get here"*.
"""

from __future__ import annotations

from enum import Enum


class OrderRequestState(str, Enum):
    """States an order request can be in (Commit 32 Part 1.3)."""

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    NORMALIZED = "NORMALIZED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    HANDOFF = "HANDOFF"
