"""
RecoveryResult — the outcome of a recovery session.

Contains the final state, verification outcome, the ramp-up level reached, all
errors that occurred and the list of actions requested from downstream services
during recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .recovery_state import RecoveryState
from .recovery_step import RecoveryAction


class VerificationStatus(str, Enum):
    """Outcome of integrity verification."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class RampUpLevel(str, Enum):
    """Gradual trading re-open levels."""

    LEVEL_0 = "LEVEL_0"
    """Reduce-only."""

    LEVEL_1 = "LEVEL_1"
    """Low-risk orders."""

    LEVEL_2 = "LEVEL_2"
    """Selected strategies."""

    LEVEL_3 = "LEVEL_3"
    """Normal trading."""

    LEVEL_4 = "LEVEL_4"
    """Full trading."""

    @classmethod
    def default(cls) -> "RampUpLevel":
        return cls.LEVEL_0


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@dataclass
class RecoveryResult:
    """Outcome of a recovery session."""

    recovery_id: str
    state: RecoveryState = RecoveryState.DETECTED
    verified: bool = False
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    ramp_up_level: RampUpLevel = RampUpLevel.LEVEL_0
    message: str = ""
    errors: List[str] = field(default_factory=list)
    actions: List[RecoveryAction] = field(default_factory=list)
    attempt: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    correlation_id: str = ""

    # -- predicates -------------------------------------------------------

    @property
    def success(self) -> bool:
        return self.state is RecoveryState.COMPLETED

    @property
    def escalated(self) -> bool:
        return self.state is RecoveryState.ESCALATED

    @property
    def failed(self) -> bool:
        return self.state in (RecoveryState.FAILED, RecoveryState.ESCALATED)

    @property
    def in_progress(self) -> bool:
        return self.state.is_active

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "state": _enum_value(self.state),
            "verified": self.verified,
            "verification_status": _enum_value(self.verification_status),
            "ramp_up_level": _enum_value(self.ramp_up_level),
            "message": self.message,
            "errors": list(self.errors),
            "actions": [a.to_dict() for a in self.actions],
            "attempt": self.attempt,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryResult":
        started = data.get("started_at")
        completed = data.get("completed_at")
        return cls(
            recovery_id=data["recovery_id"],
            state=RecoveryState(data.get("state", "DETECTED")),
            verified=data.get("verified", False),
            verification_status=VerificationStatus(
                data.get("verification_status", "UNVERIFIED")
            ),
            ramp_up_level=RampUpLevel(data.get("ramp_up_level", "LEVEL_0")),
            message=data.get("message", ""),
            errors=list(data.get("errors", [])),
            actions=[RecoveryAction.from_dict(a) for a in data.get("actions", [])],
            attempt=data.get("attempt", 0),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            correlation_id=data.get("correlation_id", ""),
        )


__all__ = ["VerificationStatus", "RampUpLevel", "RecoveryResult"]
