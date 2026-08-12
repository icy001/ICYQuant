"""
COMPONENT_STATE_CHANGED event.

Emitted whenever an individual component changes state:

    Position Service: HEALTHY → RECOVERING
    event: {
        component_id:    position_service
        previous_state:  HEALTHY
        new_state:       RECOVERING
        reason:          POSITION_RECOVERY
    }
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..domain.component_registry import ComponentType
from ..domain.component_state import ComponentState
from ..domain.system_state import StateReasonCode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ComponentStateChanged:
    """Event emitted when a component state changes."""

    component_id: str
    component_type: ComponentType
    previous_state: ComponentState
    new_state: ComponentState
    reason: StateReasonCode
    event_type: str = "COMPONENT_STATE_CHANGED"
    event_id: str = ""
    health_score: float = 100.0
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
        component_id: str,
        component_type: ComponentType,
        previous_state: ComponentState,
        new_state: ComponentState,
        reason: StateReasonCode,
        detail: str = "",
        occurred_at: Optional[datetime] = None,
    ) -> "ComponentStateChanged":
        return cls(
            component_id=component_id,
            component_type=component_type,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            detail=detail,
            occurred_at=occurred_at,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "component_id": self.component_id,
            "component_type": self.component_type.value,
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "reason": self.reason.value,
            "health_score": self.health_score,
            "detail": self.detail,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentStateChanged":
        return cls(
            event_id=data.get("event_id", ""),
            component_id=data["component_id"],
            component_type=ComponentType(data["component_type"]),
            previous_state=ComponentState(data["previous_state"]),
            new_state=ComponentState(data["new_state"]),
            reason=StateReasonCode(data["reason"]),
            health_score=float(data.get("health_score", 100.0)),
            detail=data.get("detail", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
