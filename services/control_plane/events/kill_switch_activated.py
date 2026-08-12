"""
KillSwitchActivated — a scoped kill switch became ACTIVE.

Example:

    scope: GLOBAL
    reason: EMERGENCY
    actor: operator-001
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..kill_switch.kill_switch_reason import KillSwitchReason
from ..kill_switch.kill_switch_scope import KillSwitchScope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KillSwitchActivated:
    event_type = "KILL_SWITCH_ACTIVATED"

    def __init__(
        self,
        scope: Union[KillSwitchScope, str],
        reason: Union[KillSwitchReason, str],
        actor: str,
        scope_id: Optional[str] = None,
        correlation_id: str = "",
        activated_at: Optional[datetime] = None,
    ) -> None:
        self.scope = KillSwitchScope(scope)
        self.scope_id = scope_id
        self.reason = KillSwitchReason(reason)
        self.actor = actor
        self.correlation_id = correlation_id
        self.activated_at = activated_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "reason": self.reason.value,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "activated_at": self.activated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KillSwitchActivated":
        activated_at = data.get("activated_at")
        return cls(
            scope=data["scope"],
            scope_id=data.get("scope_id"),
            reason=data["reason"],
            actor=data["actor"],
            correlation_id=data.get("correlation_id", ""),
            activated_at=datetime.fromisoformat(activated_at) if activated_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KillSwitchActivated):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"KillSwitchActivated({self.scope.value}: {self.reason.value})"
