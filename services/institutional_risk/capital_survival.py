"""CapitalSurvival — capital pool survival analysis.

The core question: "Can the capital pool survive under
current conditions and stress scenarios?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class SurvivalStatus(Enum):
    STRONG = auto()     # 90-100
    HEALTHY = auto()    # 75-90
    CAUTION = auto()    # 60-75
    DEFENSIVE = auto()  # 40-60
    CRITICAL = auto()   # <40


@dataclass
class SurvivalAssessment:
    """Capital survival assessment."""

    status: SurvivalStatus = SurvivalStatus.HEALTHY
    score: float = 100.0
    horizon_days: float = 0.0
    erosion_rate: float = 0.0  # % per day
    recovery_capacity: float = 1.0  # 0-1
    drawdown_depth: float = 0.0
    risk_budget_remaining_pct: float = 100.0
    liquidity_buffer_pct: float = 0.0
    stress_survival: float = 0.0
    warnings: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)


class CapitalSurvivalAnalyzer:
    """Analyzes capital pool survival probability.

    Comprehensive analysis of whether the capital pool can
    withstand current conditions + stress scenarios.

    Usage::

        analyzer = CapitalSurvivalAnalyzer()
        assessment = analyzer.assess(
            capital=100_000_000,
            var_99=8_000_000,
            drawdown_pct=5.0,
            es_99=12_000_000,
            risk_budget_used=7_500_000,
            risk_budget_total=8_000_000,
        )
        if assessment.status == SurvivalStatus.CRITICAL:
            print("EMERGENCY: Capital survival at risk")
    """

    def __init__(
        self,
        strong_threshold: float = 90.0,
        healthy_threshold: float = 75.0,
        caution_threshold: float = 60.0,
        defensive_threshold: float = 40.0,
    ):
        self._thresholds = {
            SurvivalStatus.STRONG: strong_threshold,
            SurvivalStatus.HEALTHY: healthy_threshold,
            SurvivalStatus.CAUTION: caution_threshold,
            SurvivalStatus.DEFENSIVE: defensive_threshold,
        }

    def assess(
        self,
        capital: float,
        var_99: float,
        drawdown_pct: float,
        es_99: float = 0.0,
        risk_budget_used: float = 0.0,
        risk_budget_total: float = 0.0,
        liquidity_score: float = 100.0,
        leverage: float = 1.0,
        daily_risk_burn: float = 0.0,
        stress_survival_score: float = 0.0,
        recovery_capacity: float = 1.0,
        margin_used: float = 0.0,
        margin_total: float = 0.0,
    ) -> SurvivalAssessment:
        """Assess capital pool survival.

        Args:
            capital: total capital pool value
            var_99: 99% Value at Risk
            drawdown_pct: current drawdown %
            es_99: 99% Expected Shortfall
            risk_budget_used: risk budget consumed
            risk_budget_total: total risk budget
            liquidity_score: liquidity quality score (0-100)
            leverage: current leverage ratio
            daily_risk_burn: estimated daily risk consumption
            stress_survival_score: survival score under stress
            recovery_capacity: ability to recover (0-1)
            margin_used: margin currently used
            margin_total: total margin available
        """
        score = 100.0
        warnings: List[str] = []
        actions: List[str] = []

        # VaR penalty
        if capital > 0:
            var_ratio = var_99 / capital * 100
            if var_ratio > 10:
                score -= (var_ratio - 10) * 2
                warnings.append(f"VaR ratio {var_ratio:.1f}% exceeds 10%")

        # ES penalty (harsher)
        if capital > 0 and es_99 > 0:
            es_ratio = es_99 / capital * 100
            if es_ratio > 12:
                score -= (es_ratio - 12) * 2.5
                warnings.append(f"ES ratio {es_ratio:.1f}% exceeds 12%")

        # drawdown penalty
        score -= drawdown_pct * 2
        if drawdown_pct > 20:
            warnings.append(f"Drawdown {drawdown_pct:.1f}% exceeds 20%")

        # risk budget consumption
        if risk_budget_total > 0:
            budget_usage = risk_budget_used / risk_budget_total * 100
            if budget_usage > 80:
                score -= (budget_usage - 80) * 0.5
                warnings.append(f"Risk budget {budget_usage:.0f}% consumed")

        # leverage penalty
        if leverage > 2.0:
            score -= (leverage - 2.0) * 10
            warnings.append(f"Leverage {leverage:.1f}x exceeds 2.0x")

        # liquidity penalty
        if liquidity_score < 60:
            score -= (60 - liquidity_score) * 0.3

        # margin stress
        if margin_total > 0:
            margin_usage = margin_used / margin_total * 100
            if margin_usage > 70:
                score -= (margin_usage - 70) * 0.4

        score = max(0.0, min(100.0, score))

        # determine status
        status = SurvivalStatus.CRITICAL
        for s, threshold in sorted(self._thresholds.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                status = s
                break

        # horizon estimation
        horizon = 0.0
        if daily_risk_burn > 0 and capital > 0:
            buffer = capital * 0.2  # assume 20% buffer before critical
            horizon = buffer / daily_risk_burn

        # recovery capacity
        if drawdown_pct > 0:
            # recovery gets harder as drawdown deepens
            recovery = max(0.0, 1.0 - drawdown_pct / 50.0)
        else:
            recovery = 1.0

        # generate actions
        actions = self._generate_actions(status, score, drawdown_pct, leverage)

        assessment = SurvivalAssessment(
            status=status,
            score=score,
            horizon_days=horizon,
            erosion_rate=daily_risk_burn / max(capital, 1e-9) * 100 if capital > 0 else 0.0,
            recovery_capacity=recovery,
            drawdown_depth=drawdown_pct,
            risk_budget_remaining_pct=(
                100 - (risk_budget_used / max(risk_budget_total, 1e-9) * 100)
            ) if risk_budget_total > 0 else 100.0,
            liquidity_buffer_pct=0.0,
            stress_survival=stress_survival_score,
            warnings=warnings,
            actions=actions,
        )
        return assessment

    def _generate_actions(
        self,
        status: SurvivalStatus,
        score: float,
        drawdown_pct: float,
        leverage: float,
    ) -> List[str]:
        """Generate survival actions based on status."""
        actions: List[str] = []

        if status == SurvivalStatus.CRITICAL:
            actions.append("EMERGENCY: Freeze all new risk")
            actions.append("Reduce leverage immediately")
            actions.append("Increase capital reserve to 40%")
            actions.append("Initiate survival stress test")
        elif status == SurvivalStatus.DEFENSIVE:
            actions.append("Freeze new risk")
            actions.append("Reduce high-beta positions")
            actions.append("Increase reserve to 25%")
        elif status == SurvivalStatus.CAUTION:
            actions.append("Monitor risk budget closely")
            actions.append("Consider reducing correlated positions")
        elif status == SurvivalStatus.HEALTHY:
            actions.append("Normal operations - maintain discipline")

        return actions
