"""
POLICY_EVALUATED event.

Emitted for every Policy Engine evaluation — the audit record that lets us
fully replay why an operational decision was made:

    policy_id(s), policy_version(s), context_snapshot, matched_rules,
    decision, actions, timestamp, correlation_id
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
class PolicyEvaluated:
    """Event emitted after every policy evaluation (audit trail)."""

    decision: PolicyDecision
    priority: PolicyPriority
    context_snapshot: Dict[str, Any]
    correlation_id: str = ""
    event_type: str = "POLICY_EVALUATED"
    event_id: str = ""
    matched_policies: List[str] = field(default_factory=list)
    policy_versions: Dict[str, str] = field(default_factory=dict)
    matched_rules: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    occurred_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_evaluation(
        cls,
        evaluation: Any,
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> "PolicyEvaluated":
        """Build from a :class:`PolicyEvaluation` result."""
        return cls(
            decision=evaluation.decision,
            priority=evaluation.priority,
            context_snapshot=context_snapshot
            if context_snapshot is not None
            else evaluation.context.to_dict(),
            correlation_id=evaluation.correlation_id,
            matched_policies=list(evaluation.matched_policies),
            policy_versions=dict(evaluation.policy_versions),
            matched_rules=list(evaluation.matched_rules),
            reasons=list(evaluation.reasons),
            actions=[a.to_dict() for a in evaluation.actions],
            occurred_at=evaluation.evaluated_at,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "decision": self.decision.value,
            "priority": self.priority.value,
            "context_snapshot": self.context_snapshot,
            "matched_policies": list(self.matched_policies),
            "policy_versions": dict(self.policy_versions),
            "matched_rules": list(self.matched_rules),
            "reasons": list(self.reasons),
            "actions": list(self.actions),
            "correlation_id": self.correlation_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyEvaluated":
        return cls(
            event_id=data.get("event_id", ""),
            decision=PolicyDecision(data["decision"]),
            priority=PolicyPriority(data["priority"]),
            context_snapshot=dict(data.get("context_snapshot", {})),
            matched_policies=list(data.get("matched_policies", [])),
            policy_versions=dict(data.get("policy_versions", {})),
            matched_rules=list(data.get("matched_rules", [])),
            reasons=list(data.get("reasons", [])),
            actions=list(data.get("actions", [])),
            correlation_id=data.get("correlation_id", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
