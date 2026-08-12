"""
Heartbeat — the periodic liveness signal sent by every critical component.

Structure:

    Heartbeat
    ├── component_id
    ├── instance_id
    ├── timestamp
    ├── sequence
    ├── status
    ├── version
    └── metadata

Idempotency: ``(component_id, instance_id, sequence)`` is the unique identity
of a heartbeat. Re-delivering the same sequence must never advance state, and
the optional ``sequence`` counter also lets the Control Plane detect gaps
(1001, 1002, 1005 → heartbeat gap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HeartbeatStatus(str, Enum):
    """Self-reported component state carried by the heartbeat."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class Heartbeat:
    """A single heartbeat emitted by a component instance."""

    component_id: str
    instance_id: str
    sequence: int
    timestamp: datetime = field(default_factory=utcnow)
    status: HeartbeatStatus = HeartbeatStatus.HEALTHY
    version: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> Tuple[str, str, int]:
        """Unique heartbeat identity: component + instance + sequence."""
        return (self.component_id, self.instance_id, self.sequence)

    def age(self, now: Optional[datetime] = None) -> float:
        """Age of this heartbeat in seconds."""
        now = now or utcnow()
        return (now - self.timestamp).total_seconds()

    def is_duplicate_of(self, other: "Heartbeat") -> bool:
        """True when ``other`` carries the same component/instance/sequence."""
        return self.identity == other.identity

    def is_stale_sequence(self, other: "Heartbeat") -> bool:
        """True when this heartbeat is older than ``other`` (out-of-order)."""
        return (
            self.component_id == other.component_id
            and self.instance_id == other.instance_id
            and self.sequence < other.sequence
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "status": self.status.value,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Heartbeat":
        ts = data.get("timestamp")
        return cls(
            component_id=data["component_id"],
            instance_id=data["instance_id"],
            sequence=data["sequence"],
            timestamp=datetime.fromisoformat(ts) if ts else utcnow(),
            status=HeartbeatStatus(data.get("status", HeartbeatStatus.HEALTHY.value)),
            version=data.get("version", ""),
            metadata=dict(data.get("metadata", {})),
        )
