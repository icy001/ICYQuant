"""Decision Guard — safety gate for allocation decisions.

Checks all decision dimensions before execution:
Capital, Risk, Capacity, Liquidity, Impact, Stress, Survival.

Output: ALLOW / RESIZE / DEFER / FREEZE / REJECT
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardResult(str, Enum):
    """Possible guard outcomes."""
    ALLOW = "ALLOW"
    RESIZE = "RESIZE"
    DEFER = "DEFER"
    FREEZE = "FREEZE"
    REJECT = "REJECT"


@dataclass
class GuardCheck:
    """Result of a single guard check."""
    check_name: str
    passed: bool = True
    value: float = 0.0
    limit: float = 0.0
    severity: str = "OK"
    message: str = ""


@dataclass
class GuardDecision:
    """Complete guard decision with all check details."""
    strategy_id: str
    decision_id: str = ""
    result: GuardResult = GuardResult.ALLOW
    checks: List[GuardCheck] = field(default_factory=list)
    failed_checks: int = 0
    reason: str = ""
    suggested_adjustment: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = [
            f"GuardDecision[{self.strategy_id}] → {self.result.value}",
            f"  Failed: {self.failed_checks}/{len(self.checks)}",
        ]
        for c in self.checks:
            status = "✓" if c.passed else "✗"
            lines.append(f"  {status} {c.check_name}: {c.message}")
        return "\n".join(lines)


class DecisionGuard:
    """Safety gate that must be passed before any autonomous allocation.

    Checks 8 dimensions:
    1. Capital adequacy
    2. Risk budget compliance
    3. Capacity headroom
    4. Liquidity sufficiency
    5. Impact budget
    6. Stress resilience
    7. Survival threshold
    8. Hysteresis check (avoid oscillation)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._checks: List[Dict[str, Any]] = []
        self._setup_default_checks()

    def _setup_default_checks(self) -> None:
        """Set up default guard checks with thresholds."""
        self._checks = [
            {
                "name": "capital_check",
                "limit": self._config.get("max_allocation_ratio", 0.95),
                "severity": "CRITICAL",
            },
            {
                "name": "risk_check",
                "limit": self._config.get("risk_budget", 0.05),
                "severity": "CRITICAL",
            },
            {
                "name": "capacity_check",
                "limit": self._config.get("capacity_threshold", 0.85),
                "severity": "HIGH",
            },
            {
                "name": "liquidity_check",
                "limit": self._config.get("liquidity_threshold", 0.20),
                "severity": "HIGH",
            },
            {
                "name": "impact_check",
                "limit": self._config.get("impact_threshold", 15.0),
                "severity": "MEDIUM",
            },
            {
                "name": "stress_check",
                "limit": self._config.get("stress_threshold", 0.25),
                "severity": "CRITICAL",
            },
            {
                "name": "survival_check",
                "limit": self._config.get("survival_threshold", 0.70),
                "severity": "CRITICAL",
            },
            {
                "name": "hysteresis_check",
                "limit": self._config.get("hysteresis_window", 0.02),
                "severity": "MEDIUM",
            },
        ]

    def guard(self, strategy_id: str, decision_id: str,
              capital_ratio: float = 0.0,
              risk_ratio: float = 0.0,
              capacity_pct: float = 0.0,
              liquidity_score: float = 0.0,
              impact_bps: float = 0.0,
              stress_drawdown: float = 0.0,
              survival_score: float = 0.0,
              weight_delta: float = 0.0) -> GuardDecision:
        """Run all guard checks and produce a decision."""

        decision = GuardDecision(strategy_id=strategy_id, decision_id=decision_id)
        checks = []

        # 1. Capital check
        cap_limit = self._get_limit("capital_check")
        cap_passed = capital_ratio <= cap_limit
        checks.append(GuardCheck(
            check_name="capital_check",
            passed=cap_passed,
            value=capital_ratio,
            limit=cap_limit,
            severity="CRITICAL" if not cap_passed else "OK",
            message=f"Capital ratio {capital_ratio:.2%} vs limit {cap_limit:.2%}",
        ))

        # 2. Risk check
        risk_limit = self._get_limit("risk_check")
        risk_passed = risk_ratio <= risk_limit
        checks.append(GuardCheck(
            check_name="risk_check",
            passed=risk_passed,
            value=risk_ratio,
            limit=risk_limit,
            severity="CRITICAL" if not risk_passed else "OK",
            message=f"Risk ratio {risk_ratio:.4f} vs limit {risk_limit:.4f}",
        ))

        # 3. Capacity check
        cap_limit2 = self._get_limit("capacity_check")
        cap_passed2 = capacity_pct <= cap_limit2
        checks.append(GuardCheck(
            check_name="capacity_check",
            passed=cap_passed2,
            value=capacity_pct,
            limit=cap_limit2,
            severity="HIGH" if not cap_passed2 else "OK",
            message=f"Capacity {capacity_pct:.1%} vs limit {cap_limit2:.1%}",
        ))

        # 4. Liquidity check
        liq_limit = self._get_limit("liquidity_check")
        liq_passed = liquidity_score >= liq_limit
        checks.append(GuardCheck(
            check_name="liquidity_check",
            passed=liq_passed,
            value=liquidity_score,
            limit=liq_limit,
            severity="HIGH" if not liq_passed else "OK",
            message=f"Liquidity {liquidity_score:.2f} vs min {liq_limit:.2f}",
        ))

        # 5. Impact check
        imp_limit = self._get_limit("impact_check")
        imp_passed = impact_bps <= imp_limit
        checks.append(GuardCheck(
            check_name="impact_check",
            passed=imp_passed,
            value=impact_bps,
            limit=imp_limit,
            severity="MEDIUM" if not imp_passed else "OK",
            message=f"Impact {impact_bps:.1f}bps vs limit {imp_limit:.1f}bps",
        ))

        # 6. Stress check
        stress_limit = self._get_limit("stress_check")
        stress_passed = stress_drawdown <= stress_limit
        checks.append(GuardCheck(
            check_name="stress_check",
            passed=stress_passed,
            value=stress_drawdown,
            limit=stress_limit,
            severity="CRITICAL" if not stress_passed else "OK",
            message=f"Stress DD {stress_drawdown:.2%} vs limit {stress_limit:.2%}",
        ))

        # 7. Survival check
        surv_limit = self._get_limit("survival_check")
        surv_passed = survival_score >= surv_limit
        checks.append(GuardCheck(
            check_name="survival_check",
            passed=surv_passed,
            value=survival_score,
            limit=surv_limit,
            severity="CRITICAL" if not surv_passed else "OK",
            message=f"Survival {survival_score:.3f} vs min {surv_limit:.3f}",
        ))

        # 8. Hysteresis check
        hyst_limit = self._get_limit("hysteresis_check")
        hyst_passed = abs(weight_delta) > hyst_limit or abs(weight_delta) < 1e-6
        checks.append(GuardCheck(
            check_name="hysteresis_check",
            passed=hyst_passed,
            value=abs(weight_delta),
            limit=hyst_limit,
            severity="MEDIUM" if not hyst_passed else "OK",
            message=f"Weight delta {abs(weight_delta):.4f} vs hysteresis {hyst_limit:.4f}",
        ))

        decision.checks = checks
        decision.failed_checks = sum(1 for c in checks if not c.passed)

        # Determine overall result
        critical_fails = sum(1 for c in checks
                             if not c.passed and c.severity == "CRITICAL")

        if critical_fails > 0:
            decision.result = GuardResult.REJECT
            decision.reason = f"{critical_fails} critical checks failed"
        elif not surv_passed:
            decision.result = GuardResult.REJECT
            decision.reason = "Survival threshold not met"
        elif not cap_passed:
            decision.result = GuardResult.RESIZE
            decision.suggested_adjustment = cap_limit / max(0.01, capital_ratio)
            decision.reason = f"Capital exceeds limit, resize to {decision.suggested_adjustment:.1%}"
        elif not liq_passed:
            decision.result = GuardResult.DEFER
            decision.reason = "Liquidity insufficient, defer"
        elif not cap_passed2:
            decision.result = GuardResult.RESIZE
            decision.reason = "Near capacity limit"
        else:
            decision.result = GuardResult.ALLOW
            decision.reason = "All checks passed"

        return decision

    def _get_limit(self, check_name: str) -> float:
        """Get the limit for a check."""
        for c in self._checks:
            if c["name"] == check_name:
                return c["limit"]
        return 0.0

    def add_check(self, name: str, limit: float,
                  severity: str = "MEDIUM") -> None:
        """Add a custom guard check."""
        self._checks.append({
            "name": name,
            "limit": limit,
            "severity": severity,
        })
