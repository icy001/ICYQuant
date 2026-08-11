"""
Policy Rule — a single evaluable rule within a policy.

For grouped rules, see: policy_rule_set.py which provides PolicyRuleSet
with evaluation modes (ALL/ANY/FIRST_FAIL/WEIGHTED) and activation conditions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

from .policy_condition import PolicyCondition, ConditionLogic, ConditionOperator


class RuleSeverity(Enum):
    """Severity levels for individual policy rules."""

    INFO = auto()
    WARNING = auto()
    REVIEW = auto()
    CRITICAL = auto()
    BLOCKING = auto()


@dataclass
class PolicyRule:
    """A single policy rule with conditions and actions."""

    rule_id: str = field(default_factory=lambda: f"RULE-{uuid.uuid4().hex[:8]}")

    # Evaluation
    metric: str = ""            # Context field to evaluate
    operator: str = "=="        # Comparison operator
    threshold: Optional[float] = None     # Static threshold
    threshold_key: Optional[str] = None    # Dynamic threshold from context

    # Severity
    severity: RuleSeverity = RuleSeverity.WARNING

    # Scope
    decision_types: List[str] = field(default_factory=list)
    scope: Optional[str] = None

    # Conditions (optional composite conditions)
    conditions: List[PolicyCondition] = field(default_factory=list)
    condition_logic: ConditionLogic = ConditionLogic.AND

    # Action on breach
    action: str = ""
    action_params: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    description: str = ""
    enabled: bool = True

    def applies_to_decision_type(self, decision_type: str) -> bool:
        if not self.decision_types:
            return True  # applies to all
        return decision_type in self.decision_types

    @property
    def effective_threshold(self) -> Optional[float]:
        return self.threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "threshold_key": self.threshold_key,
            "severity": self.severity.name,
            "decision_types": self.decision_types,
            "scope": self.scope,
            "conditions": [c.to_dict() for c in self.conditions],
            "condition_logic": self.condition_logic.name,
            "action": self.action,
            "description": self.description,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRule":
        rule = cls(
            rule_id=data.get("rule_id", ""),
            metric=data.get("metric", ""),
            operator=data.get("operator", "=="),
            threshold=data.get("threshold"),
            threshold_key=data.get("threshold_key"),
            severity=RuleSeverity[data.get("severity", "WARNING")],
            decision_types=data.get("decision_types", []),
            scope=data.get("scope"),
            condition_logic=ConditionLogic[data.get("condition_logic", "AND")],
            action=data.get("action", ""),
            action_params=data.get("action_params", {}),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
        )
        for cd in data.get("conditions", []):
            rule.conditions.append(PolicyCondition.from_dict(cd))
        return rule
