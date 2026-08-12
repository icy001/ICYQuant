"""
RecoveryStarted — a recovery session began for an incident.

The first entry of the recovery audit trail; all subsequent recovery events
carry the same recovery_id / incident_id / correlation_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryStarted:
    event_type = "RECOVERY_STARTED"

    def __init__(
        self,
        recovery_id: str,
        incident_id: str = "",
        scope: str = "",
        trigger: str = "",
        correlation_id: str = "",
        policy_version: str = "",
        started_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.incident_id = incident_id
        self.scope = scope
        self.trigger = trigger
        self.correlation_id = correlation_id
        self.policy_version = policy_version
        self.started_at = started_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "incident_id": self.incident_id,
            "scope": self.scope,
            "trigger": self.trigger,
            "correlation_id": self.correlation_id,
            "policy_version": self.policy_version,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryStarted":
        started = data.get("started_at")
        return cls(
            recovery_id=data["recovery_id"],
            incident_id=data.get("incident_id", ""),
            scope=data.get("scope", ""),
            trigger=data.get("trigger", ""),
            correlation_id=data.get("correlation_id", ""),
            policy_version=data.get("policy_version", ""),
            started_at=datetime.fromisoformat(started) if started else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryStarted):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryStarted(recovery_id={self.recovery_id!r})"
