"""DrawdownRecovery — recovery analysis and capacity estimation.

Analyzes how long and how much return is needed to recover
from a drawdown, including constraints on risk budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecoveryPlan:
    """Recovery plan from a drawdown."""

    entity_id: str
    current_drawdown_pct: float = 0.0
    recovery_needed_pct: float = 0.0
    expected_daily_return_pct: float = 0.0
    expected_recovery_days: float = 0.0
    risk_budget_available: float = 1.0
    max_risk_taking_pct: float = 0.05
    recovery_probability: float = 0.80
    feasible: bool = True
    risk_adjusted_recovery_days: float = 0.0
    constraints: List[str] = field(default_factory=list)


@dataclass
class RecoveryCapacityResult:
    """Recovery capacity analysis result."""

    capital: float
    peak_capital: float
    drawdown_pct: float
    recovery_needed_pct: float
    recovery_plans: List[RecoveryPlan] = field(default_factory=list)
    can_recover: bool = True
    estimated_recovery_months: float = 0.0
    risk_budget_constrained: bool = False
    warning: str = ""


class DrawdownRecoveryAnalyzer:
    """Analyzes recovery potential after drawdown.

    Computes how much return is needed, whether it's feasible given
    the risk budget, and estimates recovery time.

    Usage::

        analyzer = DrawdownRecoveryAnalyzer()
        plan = analyzer.plan_recovery(
            entity_id="capital",
            current_drawdown_pct=20.0,
            expected_annual_return=0.15,
            risk_budget_available=0.08,
        )
        print(f"Recovery needs {plan.recovery_needed_pct:.1f}% return")
    """

    def plan_recovery(
        self,
        entity_id: str,
        current_drawdown_pct: float,
        expected_annual_return: float = 0.15,
        expected_annual_vol: float = 0.20,
        risk_budget_available: float = 0.08,
    ) -> RecoveryPlan:
        """Create a recovery plan for a given drawdown.

        Args:
            entity_id: entity id
            current_drawdown_pct: current drawdown % (e.g., 20.0 for 20%)
            expected_annual_return: expected annual return
            expected_annual_vol: expected annual volatility
            risk_budget_available: available risk budget
        """
        # recovery needed: (1 / (1 - dd%) - 1) * 100
        recovery_needed = 100 * (1.0 / (1.0 - current_drawdown_pct / 100.0) - 1.0) if current_drawdown_pct < 100 else float("inf")

        # trading days per year
        trading_days = 252
        daily_return = expected_annual_return / trading_days
        daily_vol = expected_annual_vol / (trading_days ** 0.5)

        # expected days to recovery (simple)
        expected_recovery_days = 0.0
        if daily_return > 0:
            expected_recovery_days = (recovery_needed / 100.0) / daily_return

        # risk-adjusted recovery: account for volatility drag
        risk_adjusted_return = daily_return - 0.5 * daily_vol ** 2
        risk_adjusted_days = 0.0
        if risk_adjusted_return > 0:
            risk_adjusted_days = (recovery_needed / 100.0) / risk_adjusted_return

        # feasibility check
        feasible = True
        constraints = []

        if recovery_needed > 100.0:
            feasible = False
            constraints.append("Recovery needs >100% return")

        if expected_annual_return < current_drawdown_pct / 100.0:
            feasible = False
            constraints.append(f"Annual return {expected_annual_return:.0%} insufficient")

        # risk budget check: can we take enough risk to recover?
        recovery_probability = self._estimate_recovery_probability(
            recovery_needed_pct=recovery_needed,
            daily_return=daily_return,
            daily_vol=daily_vol,
            horizon_days=int(expected_recovery_days) if expected_recovery_days > 0 else 252,
        )

        return RecoveryPlan(
            entity_id=entity_id,
            current_drawdown_pct=current_drawdown_pct,
            recovery_needed_pct=recovery_needed,
            expected_daily_return_pct=daily_return * 100,
            expected_recovery_days=expected_recovery_days,
            risk_budget_available=risk_budget_available,
            risk_adjusted_recovery_days=risk_adjusted_days,
            recovery_probability=recovery_probability,
            feasible=feasible,
            constraints=constraints,
        )

    def _estimate_recovery_probability(
        self,
        recovery_needed_pct: float,
        daily_return: float,
        daily_vol: float,
        horizon_days: int,
    ) -> float:
        """Estimate probability of recovery within horizon.

        Uses a simple normal approximation.
        """
        import math

        if daily_vol <= 0 or horizon_days <= 0:
            return 0.5

        expected_total_return = daily_return * horizon_days
        total_vol = daily_vol * math.sqrt(horizon_days)

        # z-score for recovery target
        if total_vol > 0:
            z = (recovery_needed_pct / 100.0 - expected_total_return) / total_vol
        else:
            z = -10.0 if expected_total_return > recovery_needed_pct / 100.0 else 10.0

        # approximate CDF
        # P(Z > z) ≈ 1 - 1/(1 + exp(-1.7*z))
        prob = 1.0 / (1.0 + math.exp(-1.7 * (-z)))
        return max(0.01, min(0.99, prob))

    def analyze_capital_recovery(
        self,
        capital: float,
        peak_capital: float,
        drawdown_pct: float,
        expected_annual_return: float,
        risk_budget_remaining: float,
    ) -> RecoveryCapacityResult:
        """Analyze recovery capacity for capital pool."""
        recovery_needed = 0.0
        if drawdown_pct < 100:
            recovery_needed = 100 * (1.0 / (1.0 - drawdown_pct / 100.0) - 1.0)

        plan = self.plan_recovery(
            entity_id="capital",
            current_drawdown_pct=drawdown_pct,
            expected_annual_return=expected_annual_return,
            risk_budget_available=risk_budget_remaining,
        )

        months = plan.risk_adjusted_recovery_days / 21 if plan.risk_adjusted_recovery_days > 0 else float("inf")

        risk_constrained = risk_budget_remaining < (drawdown_pct / 100.0 * 0.3)

        warning = ""
        if not plan.feasible:
            warning = "Recovery may not be feasible with current parameters"
        elif risk_constrained:
            warning = "Risk budget may constrain recovery"

        return RecoveryCapacityResult(
            capital=capital,
            peak_capital=peak_capital,
            drawdown_pct=drawdown_pct,
            recovery_needed_pct=recovery_needed,
            recovery_plans=[plan],
            can_recover=plan.feasible,
            estimated_recovery_months=months,
            risk_budget_constrained=risk_constrained,
            warning=warning,
        )
