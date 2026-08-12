"""
KillSwitchReleased — a scoped kill switch returned to INACTIVE.

Release only happens after the release preconditions were revalidated
(system READY, risk/execution/event-bus HEALTHY, position/ledger trusted,
recovery NONE, market data FRESH).  The event carries the original reason
so the full lifecycle (activate → release) remains auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..kill_switch.kill_switch_reason import KillSwitchReason
from ..kill_switch.kill_switch_scope import KillSwitchScope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KillSwitchReleased:
    event_type = "KILL_SWITCH_RELEASED"

    def __init__(
        self,
        scope: Union[KillSwitchScope, str],
        actor: str,
        reason: Union[KillSwitchReason, str],
        scope_id: Optional[str] = None,
        correlation_id: str = "",
        released_at: Optional[datetime] = None,
    ) -> None:
        self.scope = KillSwitchScope(scope)
        self.scope_id = scope_id
        self.reason = KillSwitchReason(reason)
        self.actor = actor
        self.correlation_id = correlation_id
        self.released_at = released_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "reason": self.reason.value,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "released_at": self.released_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KillSwitchReleased":
        released_at = data.get("released_at")
        return cls(
            scope=data["scope"],
            scope_id=data.get("scope_id"),
            actor=data["actor"],
            reason=data["reason"],
            correlation_id=data.get("correlation_id", ""),
            released_at=datetime.fromisoformat(released_at) if released_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KillSwitchReleased):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"KillSwitchReleased({self.scope.value}: {self.reason.value})"
