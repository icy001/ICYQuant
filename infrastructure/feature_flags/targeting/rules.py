"""
Targeting rule models.

Defines rule data structures for the targeting
engine, including rule definitions, compiled
representations, and evaluation results.

Example:
    rule = TargetRule(
        rule_id="risk-canary-001",
        priority=10,
        expression="environment == 'production' AND broker == 'IBKR'",
        value=True,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .conditions import RuleNode


@dataclass
class TargetRule:
    """
    A targeting rule definition.

    Rules are evaluated in priority order. The first
    matching rule determines the flag's value.

    Attributes:
        rule_id: Unique rule identifier.
        priority: Evaluation priority (lower = first).
        expression: Rule expression string.
        value: Value to return when rule matches.
        enabled: Whether this rule is active.
        description: Human-readable rule description.
        tags: Tags for categorization.
        metadata: Additional key-value metadata.
        compiled_node: Compiled AST node (set by compiler).
    """

    rule_id: str = ""
    priority: int = 100
    expression: str = ""
    value: Any = True
    enabled: bool = True
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: Dict[str, Any] = field(default_factory=dict)
    compiled_node: Optional[RuleNode] = None

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "priority": self.priority,
            "expression": self.expression,
            "value": self.value,
            "enabled": self.enabled,
            "description": self.description,
            "tags": list(self.tags),
            "metadata": self.metadata,
        }


@dataclass
class RuleEvaluation:
    """
    Result of a rule evaluation.

    Attributes:
        rule_id: ID of the evaluated rule.
        matched: Whether the rule matched the context.
        value: The rule's value (if matched).
        duration_ms: Evaluation duration.
        trace: Detailed trace for diagnostics.
    """

    rule_id: str = ""
    matched: bool = False
    value: Any = None
    duration_ms: float = 0.0
    trace: List[str] = field(default_factory=list)


@dataclass
class RuleSet:
    """
    A collection of targeting rules for a feature.

    Attributes:
        flag_key: Associated feature flag key.
        rules: List of target rules.
        default_value: Default value when no rule matches.
        compiled_at: When the rules were last compiled.
        version: Rule set version for cache invalidation.
    """

    flag_key: str = ""
    rules: List[TargetRule] = field(default_factory=list)
    default_value: Any = False
    compiled_at: Optional[datetime] = None
    version: int = 0

    def get_sorted_rules(self) -> List[TargetRule]:
        """Get rules sorted by priority (lowest first)."""
        return sorted(self.rules, key=lambda r: r.priority)

    def get_enabled_rules(self) -> List[TargetRule]:
        """Get only enabled rules sorted by priority."""
        return sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: r.priority,
        )

    def to_dict(self) -> dict:
        return {
            "flag_key": self.flag_key,
            "rules": [r.to_dict() for r in self.rules],
            "default_value": self.default_value,
            "compiled_at": self.compiled_at.isoformat() if self.compiled_at else None,
            "version": self.version,
        }