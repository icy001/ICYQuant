"""
PolicyRule — one decision branch of a Policy.

    IF <condition> THEN <decision> + <actions>

A rule is the atomic unit of a policy.  Evaluation is a pure function of the
PolicyContext; rules never mutate state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .policy_action import PolicyAction, PolicyActionType
from .policy_condition import (
    CompositeCondition,
    PolicyCondition,
    _condition_from_dict,
)
from .policy_decision import PolicyDecision
from .policy_priority import PolicyPriority

Condition = Union[PolicyCondition, CompositeCondition]


@dataclass
class PolicyRule:
    """A single IF/THEN decision branch."""

    rule_id: str
    condition: Condition
    decision: PolicyDecision
    actions: List[PolicyAction] = field(default_factory=list)
    reason: str = ""
    priority: PolicyPriority = PolicyPriority.MEDIUM
    enabled: bool = True

    # -- evaluation -------------------------------------------------------

    def evaluate(self, context: Any) -> "PolicyRuleResult":
        if not self.enabled:
            return PolicyRuleResult(self.rule_id, matched=False)
        matched = self.condition.evaluate(context)
        return PolicyRuleResult(
            rule_id=self.rule_id,
            matched=matched,
            decision=self.decision if matched else None,
            actions=list(self.actions) if matched else [],
            reason=self.reason if matched else "",
            priority=self.priority if matched else None,
            condition=self.condition if matched else None,
        )

    # -- mutation helpers -------------------------------------------------

    def with_action(self, action: PolicyAction) -> "PolicyRule":
        self.actions.append(action)
        return self

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "condition": self.condition.to_dict(),
            "decision": self.decision.value,
            "actions": [a.to_dict() for a in self.actions],
            "reason": self.reason,
            "priority": self.priority.value,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRule":
        return cls(
            rule_id=data["rule_id"],
            condition=_condition_from_dict(data["condition"]),
            decision=PolicyDecision(data["decision"]),
            actions=[PolicyAction.from_dict(a) for a in data.get("actions", [])],
            reason=data.get("reason", ""),
            priority=PolicyPriority(data.get("priority", "MEDIUM")),
            enabled=data.get("enabled", True),
        )


@dataclass
class PolicyRuleResult:
    """Outcome of evaluating a single rule."""

    rule_id: str
    matched: bool
    decision: Optional[PolicyDecision] = None
    actions: List[PolicyAction] = field(default_factory=list)
    reason: str = ""
    priority: Optional[PolicyPriority] = None
    condition: Optional[Condition] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "matched": self.matched,
            "decision": self.decision.value if self.decision else None,
            "actions": [a.to_dict() for a in self.actions],
            "reason": self.reason,
            "priority": self.priority.value if self.priority else None,
        }


def action(
    action_type: PolicyActionType,
    target: str = "",
    reason: str = "",
    detail: str = "",
    priority: PolicyPriority = PolicyPriority.MEDIUM,
) -> PolicyAction:
    """Shortcut to build a PolicyAction."""
    return PolicyAction(
        action_type=action_type,
        target=target,
        reason=reason,
        detail=detail,
        priority=priority,
    )
