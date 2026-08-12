"""
Policy — a versioned, named bundle of policy rules.

Each policy carries:

    policy_id        stable identifier (e.g. ``trading-safety-policy``)
    policy_version   immutable version (e.g. ``v1.0``)

The version travels with every decision so we can always answer later:

    "which operational policy version blocked this trade?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy_action import PolicyAction
from .policy_decision import PolicyDecision, most_severe
from .policy_priority import PolicyPriority, highest_priority
from .policy_rule import PolicyRule


@dataclass
class PolicyResult:
    """Aggregated outcome of evaluating one policy."""

    policy_id: str
    policy_version: str
    matched: bool
    decision: Optional[PolicyDecision] = None
    actions: List[PolicyAction] = field(default_factory=list)
    matched_rules: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    priority: PolicyPriority = PolicyPriority.LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "matched": self.matched,
            "decision": self.decision.value if self.decision else None,
            "actions": [a.to_dict() for a in self.actions],
            "matched_rules": list(self.matched_rules),
            "reasons": list(self.reasons),
            "priority": self.priority.value,
        }


@dataclass
class Policy:
    """A versioned collection of PolicyRules."""

    policy_id: str
    policy_version: str
    name: str
    description: str = ""
    priority: PolicyPriority = PolicyPriority.MEDIUM
    rules: List[PolicyRule] = field(default_factory=list)
    enabled: bool = True

    def add_rule(self, rule: PolicyRule) -> "Policy":
        """Append a rule and return self (fluent)."""
        self.rules.append(rule)
        return self

    def with_rules(self, *rules: PolicyRule) -> "Policy":
        self.rules.extend(rules)
        return self

    # -- evaluation -------------------------------------------------------

    def evaluate(self, context: Any) -> PolicyResult:
        if not self.enabled:
            return PolicyResult(self.policy_id, self.policy_version, matched=False)

        results = [rule.evaluate(context) for rule in self.rules]
        matched = [r for r in results if r.matched]
        if not matched:
            return PolicyResult(self.policy_id, self.policy_version, matched=False)

        decisions = [r.decision for r in matched if r.decision is not None]
        final_decision = most_severe(decisions) if decisions else None

        actions: List[PolicyAction] = []
        seen = set()
        for r in matched:
            for act in r.actions:
                key = (act.action_type, act.target)
                if key not in seen:
                    seen.add(key)
                    actions.append(act)

        return PolicyResult(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            matched=True,
            decision=final_decision,
            actions=actions,
            matched_rules=[r.rule_id for r in matched],
            reasons=[r.reason for r in matched if r.reason],
            priority=highest_priority(
                [r.priority for r in matched if r.priority is not None]
            ),
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "rules": [r.to_dict() for r in self.rules],
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        return cls(
            policy_id=data["policy_id"],
            policy_version=data["policy_version"],
            name=data.get("name", data["policy_id"]),
            description=data.get("description", ""),
            priority=PolicyPriority(data.get("priority", "MEDIUM")),
            rules=[PolicyRule.from_dict(r) for r in data.get("rules", [])],
            enabled=data.get("enabled", True),
        )
