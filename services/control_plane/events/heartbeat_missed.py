"""
HeartbeatMissed — a component failed to send a heartbeat on time.

Example:

    component:    risk-engine
    last_sequence: 10231
    last_seen:    10:01:05
    detected_at:  10:01:20
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HeartbeatMissed:
    event_type = "HEARTBEAT_MISSED"

    def __init__(
        self,
        component_id: str,
        instance_id: str = "",
        last_sequence: Optional[int] = None,
        last_seen: Optional[datetime] = None,
        detected_at: Optional[datetime] = None,
        miss_count: int = 1,
        reason: str = "",
    ) -> None:
        self.component_id = component_id
        self.instance_id = instance_id
        self.last_sequence = last_sequence
        self.last_seen = last_seen
        self.detected_at = detected_at or _utcnow()
        self.miss_count = miss_count
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "component_id": self.component_id,
            "instance_id": self.instance_id,
            "last_sequence": self.last_sequence,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "detected_at": self.detected_at.isoformat(),
            "miss_count": self.miss_count,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeartbeatMissed":
        last_seen = data.get("last_seen")
        detected_at = data.get("detected_at")
        return cls(
            component_id=data["component_id"],
            instance_id=data.get("instance_id", ""),
            last_sequence=data.get("last_sequence"),
            last_seen=datetime.fromisoformat(last_seen) if last_seen else None,
            detected_at=datetime.fromisoformat(detected_at) if detected_at else None,
            miss_count=data.get("miss_count", 1),
            reason=data.get("reason", ""),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HeartbeatMissed):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"HeartbeatMissed({self.component_id}"
            f" miss={self.miss_count})"
        )
