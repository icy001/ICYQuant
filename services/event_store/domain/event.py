"""Event store domain model (Commit 34 Part 1.1 #2).

The event store keeps *facts that already happened*:

.. code-block:: text

    ORDER-001
    |-- v1 OrderCreated
    |-- v2 OrderSubmitted
    |-- v3 OrderAccepted
    `-- v4 OrderPartiallyFilled

Once appended, an event can never be modified, overwritten or renumbered - the
store is append-only (#2 / #9).  Final order / position / ledger *state* may
change, but the *history* must not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class StoredEvent:
    """An immutable fact already persisted in the event store."""

    event_id: str
    aggregate_id: str
    aggregate_type: str
    aggregate_version: int
    event_type: str
    payload: Dict[str, Any]
    correlation_id: str
    causation_id: Optional[str]
    occurred_at: datetime
    stored_at: datetime

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.aggregate_id:
            raise ValueError("aggregate_id is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if self.aggregate_version < 1:
            raise ValueError("aggregate_version must be a positive integer")
        if not self.event_type:
            raise ValueError("event_type is required")
