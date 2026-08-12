"""
HealthStatusChanged — a component's health classification changed.

Example:

    component_id: position-service
    previous:     HEALTHY
    current:      DEGRADED
    reason:       DATA_STALE
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..health.health_status import HealthStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HealthStatusChanged:
    event_type = "HEALTH_STATUS_CHANGED"

    def __init__(
        self,
        component_id: str,
        previous_status: Union[HealthStatus, str],
        current_status: Union[HealthStatus, str],
        reason: str = "",
        health_score: float = 0.0,
        instance_id: str = "",
        detected_at: Optional[datetime] = None,
    ) -> None:
        self.component_id = component_id
        self.previous_status = HealthStatus(previous_status)
        self.current_status = HealthStatus(current_status)
        self.reason = reason
        self.health_score = health_score
        self.instance_id = instance_id
        self.detected_at = detected_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "component_id": self.component_id,
            "previous_status": self.previous_status.value,
            "current_status": self.current_status.value,
            "reason": self.reason,
            "health_score": self.health_score,
            "instance_id": self.instance_id,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthStatusChanged":
        detected_at = data.get("detected_at")
        return cls(
            component_id=data["component_id"],
            previous_status=data["previous_status"],
            current_status=data["current_status"],
            reason=data.get("reason", ""),
            health_score=data.get("health_score", 0.0),
            instance_id=data.get("instance_id", ""),
            detected_at=datetime.fromisoformat(detected_at) if detected_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HealthStatusChanged):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"HealthStatusChanged({self.component_id}: "
            f"{self.previous_status.value} → {self.current_status.value})"
        )
