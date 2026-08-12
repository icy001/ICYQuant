"""
POLICY_TRIGGERED event.

Emitted whenever a rule actually fires:

    policy:      risk-critical-policy
    rule:        risk-dead-kill
    condition:   risk_engine.health == UNHEALTHY
    decision:    HALT
    action:      ACTIVATE_GLOBAL_KILL
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PolicyTriggered:
    """Event emitted when a single policy rule fires."""

    policy_id: str
    policy_version: str
    rule_id: str
    decision: PolicyDecision
    reason: str = ""
    event_type: str = "POLICY_TRIGGERED"
    event_id: str = ""
    condition: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    priority: PolicyPriority = PolicyPriority.MEDIUM
    correlation_id: str = ""
    occurred_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_rule_result(
        cls,
        policy_id: str,
        policy_version: str,
        result: Any,
        correlation_id: str = "",
    ) -> "PolicyTriggered":
        """Build from a matched :class:`PolicyRuleResult`."""
        condition = result.condition if hasattr(result, "condition") else None
        return cls(
            policy_id=policy_id,
            policy_version=policy_version,
            rule_id=result.rule_id,
            condition=condition.to_dict() if condition is not None else None,
            decision=result.decision,
            actions=[a.to_dict() for a in result.actions],
            reason=result.reason,
            priority=result.priority or PolicyPriority.MEDIUM,
            correlation_id=correlation_id,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "rule_id": self.rule_id,
            "condition": self.condition,
            "decision": self.decision.value,
            "actions": list(self.actions),
            "reason": self.reason,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyTriggered":
        return cls(
            event_id=data.get("event_id", ""),
            policy_id=data["policy_id"],
            policy_version=data["policy_version"],
            rule_id=data["rule_id"],
            condition=data.get("condition"),
            decision=PolicyDecision(data["decision"]),
            actions=list(data.get("actions", [])),
            reason=data.get("reason", ""),
            priority=PolicyPriority(data.get("priority", "MEDIUM")),
            correlation_id=data.get("correlation_id", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
