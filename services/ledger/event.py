"""
Ledger event domain model.

A LedgerEvent represents an immutable
state transition in ICYQuant.

Examples:

ORDER_FILLED
CASH_DEPOSITED
COMMISSION_CHARGED

The ledger never stores current state.
It stores facts about what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

from .event_type import LedgerEventType
from .exceptions import EventValidationError


@dataclass(frozen=True)
class LedgerEvent:
    """
    Immutable ledger event.

    Once written into ledger,
    it must never be modified.
    """

    event_type: LedgerEventType
    payload: Mapping[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)
    aggregate_id: str | None = None

    def __post_init__(self) -> None:
        """
        Validate event integrity.
        """
        if not isinstance(self.payload, Mapping):
            raise EventValidationError("payload must be mapping")

        if not self.payload:
            raise EventValidationError("event payload cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize event.

        Used by:
        - SQLite storage
        - API transport
        - Debugging
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "aggregate_id": self.aggregate_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LedgerEvent":
        """
        Deserialize event.
        """
        return cls(
            event_id=UUID(data["event_id"]),
            event_type=LedgerEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            aggregate_id=data.get("aggregate_id"),
            payload=data["payload"],
        )