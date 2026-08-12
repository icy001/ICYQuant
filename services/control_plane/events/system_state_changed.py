"""
SYSTEM_STATE_CHANGED event.

Emitted whenever the system moves between SystemState values:

    READY → DEGRADED
    event: {
        previous_state: READY
        new_state:      DEGRADED
        reason:         POSITION_RECOVERY
    }
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..domain.system_state import StateReasonCode, SystemState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SystemStateChanged:
    """Event emitted when the system state changes."""

    previous_state: SystemState
    new_state: SystemState
    reason: StateReasonCode
    source: str = "control-plane"
    event_type: str = "SYSTEM_STATE_CHANGED"
    event_id: str = ""
    detail: str = ""
    occurred_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_change(
        cls,
        previous_state: SystemState,
        new_state: SystemState,
        reason: StateReasonCode,
        source: str = "control-plane",
        detail: str = "",
        occurred_at: Optional[datetime] = None,
    ) -> "SystemStateChanged":
        return cls(
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            source=source,
            detail=detail,
            occurred_at=occurred_at,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "reason": self.reason.value,
            "source": self.source,
            "detail": self.detail,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemStateChanged":
        return cls(
            event_id=data.get("event_id", ""),
            previous_state=SystemState(data["previous_state"]),
            new_state=SystemState(data["new_state"]),
            reason=StateReasonCode(data["reason"]),
            source=data.get("source", "control-plane"),
            detail=data.get("detail", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
