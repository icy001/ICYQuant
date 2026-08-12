"""
IncidentId — typed, validated identifier for incidents.

Format:
    INC-YYYYMMDD-NNNNNN

Business layers never pass raw strings around: the ID guarantees format,
uniqueness, serialization and comparison (spec section 22).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_INCIDENT_ID_RE = re.compile(r"^INC-\d{8}-\d{6}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentId:
    """A validated incident identifier."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"IncidentId must be a string, got {type(value).__name__}"
            )
        value = value.strip()
        if not _INCIDENT_ID_RE.match(value):
            raise ValueError(
                f"Invalid incident id {value!r}: expected INC-YYYYMMDD-NNNNNN"
            )
        self.value = value

    @classmethod
    def generate(
        cls, seq: int, occurred_at: Optional[datetime] = None
    ) -> "IncidentId":
        """Generate the next incident id for a monotonically increasing sequence."""
        occurred_at = occurred_at or _utcnow()
        if seq < 0 or seq > 999999:
            raise ValueError(f"Sequence out of range for incident id: {seq}")
        return cls(f"INC-{occurred_at.strftime('%Y%m%d')}-{seq:06d}")

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {"incident_id": self.value}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentId":
        return cls(data["incident_id"])

    # -- comparison -------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentId):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"IncidentId({self.value!r})"
