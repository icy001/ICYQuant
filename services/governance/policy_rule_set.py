"""
Policy Rule Set — a named, versioned group of rules evaluated as a unit.

A RuleSet is the primary evaluation container within a PolicyVersion.
It supports activation conditions (enable/disable rules based on context),
evaluation mode (ALL/ANY/FIRST_FAIL), and result aggregation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .policy_rule import PolicyRule, RuleSeverity
from .policy_condition import PolicyCondition, ConditionLogic


class RuleSetEvaluationMode(Enum):
    """How rules within a rule set are evaluated."""

    ALL = auto()        # Evaluate all rules, aggregate all results
    ANY = auto()        # Pass if ANY rule passes
    FIRST_FAIL = auto() # Stop on first failure (fail-fast)
    WEIGHTED = auto()   # Weighted voting


class RuleSetStatus(Enum):
    """Activation status of a rule set."""

    ALWAYS = auto()     # Always active
    CONDITIONAL = auto()  # Active only when conditions are met
    FALLBACK = auto()   # Active only as a fallback
    DISABLED = auto()   # Inactive


@dataclass
class RuleEvaluation:
    """Result of evaluating a single rule within a rule set."""

    rule_id: str = ""
    rule_name: str = ""
    passed: bool = True
    severity: RuleSeverity = RuleSeverity.INFO
    metric: str = ""
    actual: Any = None
    expected: str = ""
    description: str = ""
    evaluation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity.name,
            "metric": self.metric,
            "actual": self.actual,
            "expected": self.expected,
            "description": self.description,
            "evaluation_time_ms": self.evaluation_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class RuleSetResult:
    """Aggregated result of evaluating a rule set."""

    rule_set_id: str = ""
    rule_set_name: str = ""
    passed: bool = True
    rule_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    highest_severity: RuleSeverity = RuleSeverity.INFO
    evaluations: List[RuleEvaluation] = field(default_factory=list)
    total_time_ms: float = 0.0

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    @property
    def is_blocking(self) -> bool:
        return self.highest_severity in (
            RuleSeverity.CRITICAL,
            RuleSeverity.BLOCKING,
        )

    @property
    def requires_review(self) -> bool:
        return self.highest_severity == RuleSeverity.REVIEW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_set_id": self.rule_set_id,
            "rule_set_name": self.rule_set_name,
            "passed": self.passed,
            "rule_count": self.rule_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "highest_severity": self.highest_severity.name,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "total_time_ms": self.total_time_ms,
        }


@dataclass
class PolicyRuleSet:
    """
    A named, versioned collection of policy rules evaluated as a unit.

    Rule sets support:
      - Activation conditions (enable/disable based on context)
      - Evaluation modes (ALL, ANY, FIRST_FAIL, WEIGHTED)
      - Rule grouping with shared severity thresholds
      - Weighted voting for ensemble evaluation
      - Per-rule metadata and documentation
    """

    rule_set_id: str = field(default_factory=lambda: f"RS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""

    # Rules
    rules: List[PolicyRule] = field(default_factory=list)

    # Evaluation
    evaluation_mode: RuleSetEvaluationMode = RuleSetEvaluationMode.ALL
    status: RuleSetStatus = RuleSetStatus.ALWAYS

    # Activation conditions — rule set is only active when these are met
    activation_conditions: List[PolicyCondition] = field(default_factory=list)
    activation_logic: ConditionLogic = ConditionLogic.AND

    # Weighted voting (for WEIGHTED mode)
    rule_weights: Dict[str, float] = field(default_factory=dict)
    pass_threshold: float = 0.5  # Fraction of weighted votes needed to pass

    # Sequencing
    order: int = 0  # Evaluation order within a policy
    priority: int = 0  # Priority within the policy

    # Metadata
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ---- Rule management ----

    def add_rule(self, rule: PolicyRule, weight: float = 1.0) -> None:
        """Add a rule with optional weight."""
        self.rules.append(rule)
        self.rule_weights[rule.rule_id] = weight
        self.updated_at = time.time()

    def remove_rule(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        self.rule_weights.pop(rule_id, None)
        self.updated_at = time.time()

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    def get_rule_weight(self, rule_id: str) -> float:
        return self.rule_weights.get(rule_id, 1.0)

    def set_rule_weight(self, rule_id: str, weight: float) -> None:
        self.rule_weights[rule_id] = weight
        self.updated_at = time.time()

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    @property
    def active_rules(self) -> List[PolicyRule]:
        return [r for r in self.rules if r.enabled]

    # ---- Activation check ----

    def is_active(self, context_metrics: Dict[str, Any]) -> bool:
        """Check if this rule set is active given current context metrics."""
        if self.status == RuleSetStatus.DISABLED:
            return False
        if self.status == RuleSetStatus.ALWAYS:
            return True
        if not self.activation_conditions:
            return self.status == RuleSetStatus.ALWAYS

        # Evaluate activation conditions
        results = []
        for cond in self.activation_conditions:
            value = context_metrics.get(cond.metric)
            results.append(cond.evaluate(value))

        if self.activation_logic == ConditionLogic.AND:
            return all(results)
        elif self.activation_logic == ConditionLogic.OR:
            return any(results)
        elif self.activation_logic == ConditionLogic.NOT:
            return not all(results)
        return True

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_set_id": self.rule_set_id,
            "name": self.name,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
            "evaluation_mode": self.evaluation_mode.name,
            "status": self.status.name,
            "activation_conditions": [c.to_dict() for c in self.activation_conditions],
            "activation_logic": self.activation_logic.name,
            "rule_weights": self.rule_weights,
            "pass_threshold": self.pass_threshold,
            "order": self.order,
            "priority": self.priority,
            "enabled": self.enabled,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRuleSet":
        rs = cls(
            rule_set_id=data.get("rule_set_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            evaluation_mode=RuleSetEvaluationMode[
                data.get("evaluation_mode", "ALL")
            ],
            status=RuleSetStatus[data.get("status", "ALWAYS")],
            activation_logic=ConditionLogic[
                data.get("activation_logic", "AND")
            ],
            rule_weights=data.get("rule_weights", {}),
            pass_threshold=data.get("pass_threshold", 0.5),
            order=data.get("order", 0),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        for rd in data.get("rules", []):
            rs.add_rule(PolicyRule.from_dict(rd))
        for cd in data.get("activation_conditions", []):
            rs.activation_conditions.append(PolicyCondition.from_dict(cd))
        return rs
