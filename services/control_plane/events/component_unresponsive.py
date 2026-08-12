"""
ComponentUnresponsive — a component stopped responding for too long.

After consecutive timeouts (failure hysteresis) a component moves from
DEGRADED / UNHEALTHY into UNRESPONSIVE. Only then does the higher-level
Control Plane policy react (e.g. critical component failure → TRADING_HALTED).

Example:

    Risk Engine: DEGRADED → UNHEALTHY → COMPONENT_UNRESPONSIVE
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..health.health_status import HealthStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComponentUnresponsive:
    event_type = "COMPONENT_UNRESPONSIVE"

    def __init__(
        self,
        component_id: str,
        instance_id: str = "",
        previous_health: Union[HealthStatus, str, None] = None,
        current_health: Union[HealthStatus, str, None] = None,
        reason: str = "",
        detected_at: Optional[datetime] = None,
    ) -> None:
        self.component_id = component_id
        self.instance_id = instance_id
        self.previous_health = (
            HealthStatus(previous_health) if previous_health else HealthStatus.UNKNOWN
        )
        self.current_health = (
            HealthStatus(current_health) if current_health else HealthStatus.UNHEALTHY
        )
        self.reason = reason
        self.detected_at = detected_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "component_id": self.component_id,
            "instance_id": self.instance_id,
            "previous_health": self.previous_health.value,
            "current_health": self.current_health.value,
            "reason": self.reason,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentUnresponsive":
        detected_at = data.get("detected_at")
        return cls(
            component_id=data["component_id"],
            instance_id=data.get("instance_id", ""),
            previous_health=data.get("previous_health"),
            current_health=data.get("current_health"),
            reason=data.get("reason", ""),
            detected_at=datetime.fromisoformat(detected_at) if detected_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ComponentUnresponsive):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"ComponentUnresponsive({self.component_id}: "
            f"{self.previous_health.value} → {self.current_health.value})"
        )
