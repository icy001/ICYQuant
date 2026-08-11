"""SurvivalScore — composite survival score computation.

Aggregates multiple risk dimensions into a single 0-100 score
that measures capital pool survivability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SurvivalScoreInput:
    """Inputs for survival score computation."""

    capital: float = 0.0
    var_99: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    leverage: float = 1.0
    liquidity_score: float = 100.0
    tail_risk_score: float = 0.0
    correlation_risk: float = 0.0
    risk_budget_used_pct: float = 0.0
    margin_usage_pct: float = 0.0
    recovery_capacity: float = 1.0
    concentration_score: float = 1.0


@dataclass
class SurvivalScoreOutput:
    """Survival score output."""

    score: float = 100.0
    components: Dict[str, float] = field(default_factory=dict)
    level: str = "STRONG"  # STRONG, HEALTHY, CAUTION, DEFENSIVE, CRITICAL
    primary_drag: str = ""
    recommendations: List[str] = field(default_factory=list)


class SurvivalScoreEngine:
    """Computes composite capital survival score.

    Score = base - penalties from:
    - VaR ratio
    - ES ratio
    - Drawdown
    - Leverage
    - Liquidity
    - Tail risk
    - Correlation risk
    - Risk budget usage
    - Margin usage
    - Concentration

    Usage::

        engine = SurvivalScoreEngine()
        result = engine.compute(SurvivalScoreInput(
            capital=100_000_000,
            var_99=8_000_000,
            drawdown_pct=5.0,
        ))
        print(f"Survival: {result.score}/100 ({result.level})")
    """

    def __init__(
        self,
        strong_threshold: float = 90.0,
        healthy_threshold: float = 75.0,
        caution_threshold: float = 60.0,
        defensive_threshold: float = 40.0,
    ):
        self._strong = strong_threshold
        self._healthy = healthy_threshold
        self._caution = caution_threshold
        self._defensive = defensive_threshold

    def compute(self, inputs: SurvivalScoreInput) -> SurvivalScoreOutput:
        """Compute survival score from inputs."""
        score = 100.0
        components: Dict[str, float] = {}
        max_drag = 0.0
        primary = ""

        def _penalize(name: str, penalty: float, weight: float = 1.0) -> float:
            nonlocal max_drag, primary
            p = penalty * weight
            if p > max_drag:
                max_drag = p
                primary = name
            return p

        # VaR penalty
        if inputs.capital > 0:
            var_ratio = inputs.var_99 / inputs.capital
            var_drag = _penalize("VaR", min(var_ratio * 100 * 2, 30.0))
            score -= var_drag
            components["var_penalty"] = var_drag

        # ES penalty
        if inputs.capital > 0 and inputs.expected_shortfall_99 > 0:
            es_ratio = inputs.expected_shortfall_99 / inputs.capital
            es_drag = _penalize("Expected Shortfall", min(es_ratio * 100 * 2.5, 30.0))
            score -= es_drag
            components["es_penalty"] = es_drag

        # drawdown penalty
        dd_drag = _penalize("Drawdown", min(inputs.drawdown_pct * 2.0, 40.0))
        score -= dd_drag
        components["drawdown_penalty"] = dd_drag

        # max drawdown penalty
        mdd_drag = _penalize("Max Drawdown", min(inputs.max_drawdown_pct * 1.0, 20.0))
        score -= mdd_drag
        components["max_drawdown_penalty"] = mdd_drag

        # leverage penalty
        if inputs.leverage > 1.5:
            lev_drag = _penalize("Leverage", min((inputs.leverage - 1.0) * 15, 25.0))
            score -= lev_drag
            components["leverage_penalty"] = lev_drag

        # liquidity penalty
        if inputs.liquidity_score < 70:
            liq_drag = _penalize("Liquidity", min((70 - inputs.liquidity_score) * 0.4, 15.0))
            score -= liq_drag
            components["liquidity_penalty"] = liq_drag

        # tail risk penalty
        tail_drag = _penalize("Tail Risk", min(inputs.tail_risk_score * 0.3, 20.0))
        score -= tail_drag
        components["tail_risk_penalty"] = tail_drag

        # correlation risk penalty
        corr_drag = _penalize("Correlation", min(inputs.correlation_risk * 30, 20.0))
        score -= corr_drag
        components["correlation_penalty"] = corr_drag

        # risk budget penalty
        if inputs.risk_budget_used_pct > 70:
            budget_drag = _penalize("Risk Budget", min((inputs.risk_budget_used_pct - 70) * 0.3, 15.0))
            score -= budget_drag
            components["risk_budget_penalty"] = budget_drag

        # margin penalty
        if inputs.margin_usage_pct > 60:
            margin_drag = _penalize("Margin", min((inputs.margin_usage_pct - 60) * 0.3, 15.0))
            score -= margin_drag
            components["margin_penalty"] = margin_drag

        # recovery bonus (positive!)
        recovery_bonus = inputs.recovery_capacity * 10
        score += recovery_bonus
        components["recovery_bonus"] = recovery_bonus

        score = max(0.0, min(100.0, score))

        # level
        level = "CRITICAL"
        if score >= self._strong:
            level = "STRONG"
        elif score >= self._healthy:
            level = "HEALTHY"
        elif score >= self._caution:
            level = "CAUTION"
        elif score >= self._defensive:
            level = "DEFENSIVE"

        # recommendations
        recs = []
        if inputs.leverage > 2.0:
            recs.append("Reduce leverage below 2.0x")
        if inputs.drawdown_pct > 15:
            recs.append("Consider reducing positions to limit drawdown")
        if inputs.risk_budget_used_pct > 80:
            recs.append("Risk budget nearly exhausted — freeze new risk")
        if inputs.correlation_risk > 0.5:
            recs.append("High correlation risk — reduce correlated clusters")

        return SurvivalScoreOutput(
            score=score,
            components=components,
            level=level,
            primary_drag=primary,
            recommendations=recs,
        )
