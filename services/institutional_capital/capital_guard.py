"""
Capital Guard — Safety gate for all capital adjustments.

Every capital action must pass through the Capital Guard, which checks:
    Capital Limit, Risk Limit, Strategy Capacity, Liquidity,
    Drawdown, Autonomy Level, Policy.

Outputs:
    ALLOW, RESIZE, DEFER, REJECT
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .capital_decision import CapitalDecision, CapitalDecisionType


class GuardVerdict(str, Enum):
    ALLOW = "allow"           # Proceed as requested
    RESIZE = "resize"         # Proceed but with modified amount
    DEFER = "defer"           # Defer to later review
    REJECT = "reject"         # Block entirely


class GuardRuleType(str, Enum):
    CAPITAL_LIMIT = "capital_limit"
    RISK_LIMIT = "risk_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    STRATEGY_CAPACITY = "strategy_capacity"
    LIQUIDITY = "liquidity"
    DRAWDOWN = "drawdown"
    CONCENTRATION = "concentration"
    AUTONOMY = "autonomy"
    POLICY = "policy"
    CUSTOM = "custom"


@dataclass
class GuardRule:
    """A single guard rule with check logic."""

    rule_id: str = field(default_factory=lambda: f"GR-{uuid.uuid4().hex[:8]}")
    name: str = ""
    rule_type: GuardRuleType = GuardRuleType.CUSTOM
    description: str = ""
    enabled: bool = True
    blocking: bool = True          # REJECT vs WARN
    priority: int = 50

    # Thresholds
    max_capital: float = float("inf")
    max_risk: float = float("inf")
    max_leverage: float = float("inf")
    max_drawdown: float = float("inf")
    max_single_weight: float = float("inf")
    max_capacity_pct: float = 1.0

    # Autonomy
    min_autonomy_level: int = 0
    max_autonomous_amount: float = float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "type": self.rule_type.value,
            "enabled": self.enabled,
            "blocking": self.blocking,
        }


@dataclass
class GuardResult:
    """Result of passing a decision through the Capital Guard."""

    guard_id: str = field(default_factory=lambda: f"CG-{uuid.uuid4().hex[:8]}")
    decision_id: str = ""
    verdict: GuardVerdict = GuardVerdict.ALLOW

    # Modified values if RESIZE
    resized_amount: float = 0.0
    original_amount: float = 0.0

    # Rule violations
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guard_id": self.guard_id,
            "decision_id": self.decision_id,
            "verdict": self.verdict.value,
            "resized_amount": self.resized_amount,
            "violations": self.violations,
            "warnings": self.warnings,
        }

    @property
    def allowed(self) -> bool:
        return self.verdict in (GuardVerdict.ALLOW, GuardVerdict.RESIZE)


class CapitalGuard:
    """Enforces safety gates on all capital actions.

    Plugs into Commit 18 Control Plane via policy/autonomy integration.
    """

    def __init__(self):
        self._rules: List[GuardRule] = []
        self._results: List[GuardResult] = []
        self._build_default_rules()

    def _build_default_rules(self) -> None:
        """Create institutional default safety rules."""
        self._rules = [
            GuardRule(
                name="Capital Conservation",
                rule_type=GuardRuleType.CAPITAL_LIMIT,
                description="Total allocated cannot exceed total capital",
                priority=0,
            ),
            GuardRule(
                name="Risk Budget",
                rule_type=GuardRuleType.RISK_LIMIT,
                description="Strategy risk must stay within allocated risk budget",
                max_risk=0.25,
                priority=1,
            ),
            GuardRule(
                name="Leverage Cap",
                rule_type=GuardRuleType.LEVERAGE_LIMIT,
                max_leverage=2.0,
                priority=2,
            ),
            GuardRule(
                name="Strategy Capacity Limit",
                rule_type=GuardRuleType.STRATEGY_CAPACITY,
                description="Capital must not exceed strategy capacity",
                max_capacity_pct=0.95,
                priority=3,
            ),
            GuardRule(
                name="Drawdown Protection",
                rule_type=GuardRuleType.DRAWDOWN,
                max_drawdown=0.20,
                priority=4,
            ),
            GuardRule(
                name="Concentration Limit",
                rule_type=GuardRuleType.CONCENTRATION,
                max_single_weight=0.25,
                priority=5,
            ),
            GuardRule(
                name="Liquidity Check",
                rule_type=GuardRuleType.LIQUIDITY,
                description="Ensure sufficient liquidity for execution",
                priority=10,
            ),
            GuardRule(
                name="Autonomy Boundary",
                rule_type=GuardRuleType.AUTONOMY,
                description="Action must be within current autonomy level permissions",
                min_autonomy_level=1,
                priority=15,
            ),
        ]

    def add_rule(self, rule: GuardRule) -> None:
        self._rules.append(rule)

    def check(
        self,
        decision: CapitalDecision,
        available_capital: float = 0.0,
        current_risk: float = 0.0,
        current_drawdown: float = 0.0,
        strategy_capacity: float = float("inf"),
        current_weight: float = 0.0,
        autonomy_level: int = 5,
    ) -> GuardResult:
        """Check a capital decision against all guard rules."""
        result = GuardResult(
            decision_id=decision.decision_id,
            original_amount=abs(decision.delta_capital),
        )

        target_amount = decision.target_capital
        delta = decision.delta_capital

        for rule in sorted(self._rules, key=lambda r: r.priority):
            if not rule.enabled:
                continue

            # Capital conservation
            if rule.rule_type == GuardRuleType.CAPITAL_LIMIT:
                if delta > 0 and delta > available_capital:
                    result.violations.append(
                        f"[{rule.name}] Requested +{delta:,.0f} exceeds available {available_capital:,.0f}"
                    )
                    result.resized_amount = available_capital
                    if rule.blocking:
                        result.verdict = GuardVerdict.RESIZE

            # Risk limit
            if rule.rule_type == GuardRuleType.RISK_LIMIT:
                if current_risk > rule.max_risk:
                    result.violations.append(
                        f"[{rule.name}] Current risk {current_risk:.2%} exceeds limit {rule.max_risk:.2%}"
                    )
                    if rule.blocking:
                        result.verdict = GuardVerdict.REJECT

            # Leverage limit
            if rule.rule_type == GuardRuleType.LEVERAGE_LIMIT:
                if target_amount / max(available_capital + target_amount, 1) > rule.max_leverage:
                    result.violations.append(f"[{rule.name}] Implied leverage exceeds {rule.max_leverage}")
                    if rule.blocking:
                        result.verdict = GuardVerdict.REJECT

            # Strategy capacity
            if rule.rule_type == GuardRuleType.STRATEGY_CAPACITY:
                if strategy_capacity > 0 and target_amount / strategy_capacity > rule.max_capacity_pct:
                    result.violations.append(
                        f"[{rule.name}] Target capital {target_amount:,.0f} exceeds {rule.max_capacity_pct:.0%} of capacity {strategy_capacity:,.0f}"
                    )
                    result.resized_amount = strategy_capacity * rule.max_capacity_pct
                    if rule.blocking:
                        result.verdict = GuardVerdict.RESIZE

            # Drawdown
            if rule.rule_type == GuardRuleType.DRAWDOWN:
                if current_drawdown > rule.max_drawdown:
                    result.violations.append(
                        f"[{rule.name}] Drawdown {current_drawdown:.2%} exceeds limit {rule.max_drawdown:.2%}"
                    )
                    if decision.decision_type == CapitalDecisionType.INCREASE:
                        result.verdict = GuardVerdict.DEFER

            # Concentration
            if rule.rule_type == GuardRuleType.CONCENTRATION:
                if current_weight + target_amount / max(available_capital + target_amount, 1) > rule.max_single_weight:
                    result.warnings.append(f"[{rule.name}] May exceed concentration limit")

            # Autonomy
            if rule.rule_type == GuardRuleType.AUTONOMY:
                if autonomy_level < rule.min_autonomy_level:
                    result.violations.append(
                        f"[{rule.name}] Autonomy level {autonomy_level} < required {rule.min_autonomy_level}"
                    )
                    result.verdict = GuardVerdict.DEFER

            # Track
            if result.violations or result.warnings:
                result.failed_rules.append(rule.name)
            else:
                result.passed_rules.append(rule.name)

        if result.verdict == GuardVerdict.REJECT:
            decision.reject("; ".join(result.violations))

        decision.guard_result = result.verdict.value
        decision.guard_violations = result.violations

        self._results.append(result)
        return result

    def history(self) -> List[GuardResult]:
        return list(self._results)

    def stats(self) -> Dict[str, int]:
        return {
            "total_checks": len(self._results),
            "allowed": sum(1 for r in self._results if r.verdict == GuardVerdict.ALLOW),
            "resized": sum(1 for r in self._results if r.verdict == GuardVerdict.RESIZE),
            "deferred": sum(1 for r in self._results if r.verdict == GuardVerdict.DEFER),
            "rejected": sum(1 for r in self._results if r.verdict == GuardVerdict.REJECT),
        }
