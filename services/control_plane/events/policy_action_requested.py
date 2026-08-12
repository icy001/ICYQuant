"""
POLICY_ACTION_REQUESTED event.

Emitted when the Policy Engine requests a concrete action.  The engine never
executes complex actions itself — it hands the request to the owning
subsystem:

    ACTION: START_RECOVERY        → Recovery Engine
    ACTION: ACTIVATE_KILL_SWITCH  → Kill Switch
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..policy.policy_action import PolicyAction, PolicyActionType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PolicyActionRequested:
    """Event emitted when a policy action is handed to a subsystem."""

    action_type: PolicyActionType
    target: str = ""
    policy_id: str = ""
    policy_version: str = ""
    reason: str = ""
    detail: str = ""
    event_type: str = "POLICY_ACTION_REQUESTED"
    event_id: str = ""
    status: str = "REQUESTED"
    correlation_id: str = ""
    occurred_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_action(
        cls,
        action: PolicyAction,
        policy_id: str = "",
        policy_version: str = "",
        correlation_id: str = "",
        status: str = "REQUESTED",
    ) -> "PolicyActionRequested":
        return cls(
            action_type=action.action_type,
            target=action.target,
            policy_id=policy_id,
            policy_version=policy_version,
            reason=action.reason,
            detail=action.detail,
            status=status,
            correlation_id=correlation_id,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "reason": self.reason,
            "detail": self.detail,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyActionRequested":
        return cls(
            event_id=data.get("event_id", ""),
            action_type=PolicyActionType(data["action_type"]),
            target=data.get("target", ""),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            reason=data.get("reason", ""),
            detail=data.get("detail", ""),
            status=data.get("status", "REQUESTED"),
            correlation_id=data.get("correlation_id", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
