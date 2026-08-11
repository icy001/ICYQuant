"""RecoveryCapacity — assess ability to recover from drawdown.

Evaluates whether current parameters (return, risk, capacity)
support recovery from the current drawdown level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecoveryCapacityResult:
    """Recovery capacity assessment."""

    current_drawdown_pct: float = 0.0
    recovery_needed_pct: float = 0.0
    expected_annual_return: float = 0.0
    expected_recovery_months: float = 0.0
    risk_adjusted_recovery_months: float = 0.0
    max_feasible_drawdown: float = 0.0
    recovery_feasible: bool = True
    risk_budget_available_for_recovery: float = 0.0
    constraints: List[str] = field(default_factory=list)
    recommendation: str = ""


class RecoveryCapacityAnalyzer:
    """Analyzes recovery capacity after drawdown.

    Usage::

        analyzer = RecoveryCapacityAnalyzer()
        result = analyzer.analyze(
            drawdown_pct=20.0,
            expected_annual_return=0.15,
            expected_annual_vol=0.20,
            risk_budget_remaining=0.05,
        )
        print(f"Recovery: {result.recovery_needed_pct:.1f}% needed")
    """

    def analyze(
        self,
        drawdown_pct: float,
        expected_annual_return: float,
        expected_annual_vol: float = 0.20,
        risk_budget_remaining: float = 0.08,
        max_recovery_time_months: float = 24.0,
    ) -> RecoveryCapacityResult:
        """Analyze recovery capacity.

        Args:
            drawdown_pct: current drawdown percentage
            expected_annual_return: expected annual return
            expected_annual_vol: expected annual volatility
            risk_budget_remaining: remaining risk budget
            max_recovery_time_months: max acceptable recovery time
        """
        # recovery needed
        if drawdown_pct < 100:
            recovery_needed = 100 * (1.0 / (1.0 - drawdown_pct / 100.0) - 1.0)
        else:
            recovery_needed = float("inf")

        # simple expected recovery (months)
        monthly_return = expected_annual_return / 12
        simple_months = float("inf")
        if monthly_return > 0:
            simple_months = (recovery_needed / 100.0) / monthly_return

        # risk-adjusted (account for volatility drag)
        monthly_vol = expected_annual_vol / (12 ** 0.5)
        risk_adj_monthly = monthly_return - 0.5 * monthly_vol ** 2
        risk_adj_months = float("inf")
        if risk_adj_monthly > 0:
            risk_adj_months = (recovery_needed / 100.0) / risk_adj_monthly

        # maximum feasible drawdown: at what drawdown is recovery impossible?
        max_feasible = 0.0
        if expected_annual_return > 0:
            # approximate: max dd where recovery takes < max_recovery_time
            monthly = expected_annual_return / 12
            max_ret = monthly * max_recovery_time_months
            # ret = (1/(1-dd) - 1) → dd = 1 - 1/(1+ret)
            max_feasible = (1.0 - 1.0 / (1.0 + max_ret)) * 100

        # feasibility check
        feasible = True
        constraints: List[str] = []

        if recovery_needed > 100:
            feasible = False
            constraints.append("Recovery needs >100% return")

        if risk_adj_months > max_recovery_time_months:
            feasible = False
            constraints.append(
                f"Risk-adjusted recovery ({risk_adj_months:.0f}mo) "
                f"exceeds max ({max_recovery_time_months:.0f}mo)"
            )

        if risk_budget_remaining < 0.02:
            constraints.append("Risk budget too low for aggressive recovery")

        # recommendation
        recommendation = "Continue normal operations"
        if not feasible:
            recommendation = (
                "RECOVERY RISK: Current parameters cannot support recovery. "
                "Consider reducing positions, increasing capital, or accepting losses."
            )
        elif risk_adj_months > 12:
            recommendation = (
                f"Extended recovery ({risk_adj_months:.0f} months). "
                "Consider defensive positioning."
            )

        return RecoveryCapacityResult(
            current_drawdown_pct=drawdown_pct,
            recovery_needed_pct=recovery_needed,
            expected_annual_return=expected_annual_return,
            expected_recovery_months=simple_months,
            risk_adjusted_recovery_months=risk_adj_months,
            max_feasible_drawdown=max_feasible,
            recovery_feasible=feasible,
            risk_budget_available_for_recovery=risk_budget_remaining,
            constraints=constraints,
            recommendation=recommendation,
        )
