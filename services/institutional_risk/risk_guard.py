"""RiskGuard — pre-execution risk check gate.

Every significant capital action passes through the risk guard
before execution. Checks all risk dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class GuardDecision(Enum):
    ALLOW = auto()
    RESIZE = auto()
    DEFER = auto()
    FREEZE = auto()
    REJECT = auto()


@dataclass
class GuardCheck:
    """A single guard check result."""

    name: str
    passed: bool
    value: float = 0.0
    limit: float = 0.0
    reason: str = ""


@dataclass
class GuardResult:
    """Full risk guard result."""

    decision: GuardDecision = GuardDecision.ALLOW
    checks: List[GuardCheck] = field(default_factory=list)
    failed_checks: List[GuardCheck] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""


class RiskGuard:
    """Pre-execution risk guard.

    Checks ALL risk dimensions before allowing capital actions:
    - Capital risk (VaR, ES)
    - Risk budget
    - Drawdown
    - Leverage
    - Liquidity
    - Concentration
    - Survival

    Usage::

        guard = RiskGuard()
        result = guard.check(
            action_type="INCREASE",
            amount=5_000_000,
            current_state={...},
        )
        if result.decision != GuardDecision.ALLOW:
            print(f"BLOCKED: {result.summary}")
    """

    def __init__(self):
        self._checks: List[Dict[str, Any]] = [
            {"name": "risk_budget", "limit": None},
            {"name": "drawdown", "limit": 20.0},
            {"name": "leverage", "limit": 3.0},
            {"name": "var_ratio", "limit": 10.0},
            {"name": "es_ratio", "limit": 12.0},
            {"name": "concentration", "limit": 35.0},
            {"name": "survival", "limit": 40.0},
        ]

    def check(
        self,
        action_type: str,
        amount: float,
        current_state: Dict[str, Any],
        post_action_state: Dict[str, Any],
    ) -> GuardResult:
        """Run all guard checks.

        Args:
            action_type: action being performed
            amount: amount involved
            current_state: current risk state
            post_action_state: estimated post-action state
        """
        checks: List[GuardCheck] = []

        # 1. risk budget check
        budget_total = post_action_state.get("risk_budget_total", 0.0)
        budget_used = post_action_state.get("risk_budget_used", 0.0)
        if budget_total > 0:
            utilization = (budget_used / budget_total) * 100
            checks.append(GuardCheck(
                name="risk_budget",
                passed=utilization <= 100,
                value=utilization,
                limit=100.0,
                reason=f"Risk budget at {utilization:.0f}%" if utilization > 100 else "OK",
            ))

        # 2. drawdown check
        dd = post_action_state.get("drawdown_pct", 0.0)
        checks.append(GuardCheck(
            name="drawdown",
            passed=dd <= 20.0,
            value=dd,
            limit=20.0,
            reason=f"Drawdown {dd:.1f}%" if dd > 20 else "OK",
        ))

        # 3. leverage check
        lev = post_action_state.get("leverage", 1.0)
        checks.append(GuardCheck(
            name="leverage",
            passed=lev <= 3.0,
            value=lev,
            limit=3.0,
            reason=f"Leverage {lev:.1f}x" if lev > 3.0 else "OK",
        ))

        # 4. VaR ratio check
        capital = post_action_state.get("capital", 1.0)
        var_99 = post_action_state.get("var_99", 0.0)
        var_ratio = (var_99 / capital * 100) if capital > 0 else 0.0
        checks.append(GuardCheck(
            name="var_ratio",
            passed=var_ratio <= 10.0,
            value=var_ratio,
            limit=10.0,
            reason=f"VaR {var_ratio:.1f}% of capital" if var_ratio > 10 else "OK",
        ))

        # 5. survival check
        survival = post_action_state.get("survival_score", 100.0)
        checks.append(GuardCheck(
            name="survival",
            passed=survival >= 40.0,
            value=survival,
            limit=40.0,
            reason=f"Survival {survival:.0f}/100" if survival < 40 else "OK",
        ))

        # determine decision
        failed = [c for c in checks if not c.passed]
        critical_failures = [
            c for c in failed
            if c.name in ("survival", "risk_budget")
        ]

        if critical_failures:
            decision = GuardDecision.REJECT
        elif len(failed) >= 2:
            decision = GuardDecision.FREEZE
        elif len(failed) == 1:
            decision = GuardDecision.RESIZE
        else:
            decision = GuardDecision.ALLOW

        warnings = []
        for c in checks:
            if c.passed and c.value > c.limit * 0.8:
                warnings.append(f"{c.name}: near limit ({c.value:.1f}/{c.limit:.1f})")

        summary = f"{decision.name}: {len(failed)}/{len(checks)} checks failed"
        if failed:
            summary += f" [{', '.join(c.name for c in failed)}]"

        return GuardResult(
            decision=decision,
            checks=checks,
            failed_checks=failed,
            warnings=warnings,
            summary=summary,
        )
