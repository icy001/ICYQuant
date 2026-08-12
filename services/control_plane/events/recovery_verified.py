"""
RecoveryVerified — integrity verification finished for a recovery.

Only a ``verified=True`` recovery may proceed to RAMPING_UP.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryVerified:
    event_type = "RECOVERY_VERIFIED"

    def __init__(
        self,
        recovery_id: str,
        verified: bool = False,
        checks: Dict[str, Any] | None = None,
        correlation_id: str = "",
        verified_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.verified = verified
        self.checks = dict(checks or {})
        self.correlation_id = correlation_id
        self.verified_at = verified_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "verified": self.verified,
            "checks": dict(self.checks),
            "correlation_id": self.correlation_id,
            "verified_at": self.verified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryVerified":
        verified_at = data.get("verified_at")
        return cls(
            recovery_id=data["recovery_id"],
            verified=data.get("verified", False),
            checks=dict(data.get("checks", {})),
            correlation_id=data.get("correlation_id", ""),
            verified_at=datetime.fromisoformat(verified_at) if verified_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryVerified):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryVerified(verified={self.verified})"
