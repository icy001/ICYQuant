"""SurvivalHorizon — estimate how long capital can survive.

Answers: "At the current risk burn rate, how long until
the risk budget is exhausted?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SurvivalHorizonResult:
    """Survival horizon estimate."""

    current_capital: float = 0.0
    risk_budget_total: float = 0.0
    risk_budget_remaining: float = 0.0
    daily_risk_burn: float = 0.0
    days_to_exhaustion: float = 0.0
    weeks_to_exhaustion: float = 0.0
    months_to_exhaustion: float = 0.0
    critical_level: float = 0.0  # capital level that triggers critical
    days_to_critical: float = 0.0
    status: str = "NORMAL"
    recommendation: str = ""


class SurvivalHorizonEstimator:
    """Estimates capital survival horizon.

    Usage::

        est = SurvivalHorizonEstimator()
        result = est.estimate(
            capital=100_000_000,
            daily_risk_burn=500_000,
            risk_budget_remaining=5_000_000,
            risk_budget_total=8_000_000,
        )
        print(f"Days to exhaustion: {result.days_to_exhaustion:.0f}")
    """

    def __init__(
        self,
        critical_capital_ratio: float = 0.50,
        warning_days: float = 30.0,
        critical_days: float = 10.0,
    ):
        self._critical_ratio = critical_capital_ratio
        self._warning_days = warning_days
        self._critical_days = critical_days

    def estimate(
        self,
        capital: float,
        daily_risk_burn: float,
        risk_budget_remaining: float = 0.0,
        risk_budget_total: float = 0.0,
        daily_expected_return: float = 0.0,
    ) -> SurvivalHorizonResult:
        """Estimate survival horizon.

        Args:
            capital: current capital pool value
            daily_risk_burn: daily risk consumed (in value terms)
            risk_budget_remaining: remaining risk budget
            risk_budget_total: total risk budget
            daily_expected_return: expected daily return (offsets burn)
        """
        net_burn = max(0.0, daily_risk_burn - daily_expected_return)

        # days to exhaust risk budget
        days_risk = float("inf")
        if net_burn > 0 and risk_budget_remaining > 0:
            days_risk = risk_budget_remaining / net_burn

        # days to critical capital level
        critical_capital = capital * self._critical_ratio
        days_critical = float("inf")
        if net_burn > 0:
            days_critical = (capital - critical_capital) / net_burn

        # status
        status = "NORMAL"
        if days_critical <= self._critical_days:
            status = "CRITICAL"
        elif days_critical <= self._warning_days:
            status = "WARNING"

        # recommendation
        recommendation = "Normal operations"
        if status == "CRITICAL":
            recommendation = (
                f"IMMEDIATE ACTION: Only {days_critical:.0f} days until critical. "
                "Reduce risk, increase reserve, freeze new positions."
            )
        elif status == "WARNING":
            recommendation = (
                f"CAUTION: {days_critical:.0f} days until critical. "
                "Consider reducing risk burn rate."
            )

        return SurvivalHorizonResult(
            current_capital=capital,
            risk_budget_total=risk_budget_total,
            risk_budget_remaining=risk_budget_remaining,
            daily_risk_burn=net_burn,
            days_to_exhaustion=days_risk,
            weeks_to_exhaustion=days_risk / 5 if days_risk != float("inf") else float("inf"),
            months_to_exhaustion=days_risk / 21 if days_risk != float("inf") else float("inf"),
            critical_level=critical_capital,
            days_to_critical=days_critical,
            status=status,
            recommendation=recommendation,
        )
