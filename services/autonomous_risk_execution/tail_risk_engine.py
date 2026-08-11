"""
Tail Risk Engine — measures and monitors extreme tail event risks.

Beyond normal volatility, this engine focuses on:
    - Gap risk (overnight/weekend moves)
    - Crash risk (rapid large declines)
    - Liquidity shock risk
    - Correlation spike risk
    - Volatility explosion risk

Key metrics:
    - Tail beta (sensitivity to tail events)
    - Conditional tail expectation
    - Maximum adverse excursion
    - Tail dependence coefficients
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class TailRiskMetrics:
    """Tail risk measurement."""
    id: str = field(default_factory=lambda: str(uuid4()))
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    max_adverse_excursion: float = 0.0
    tail_beta: float = 1.0
    skewness: float = 0.0
    excess_kurtosis: float = 0.0
    var_ratio: float = 1.0  # ES / VaR — higher = fatter tails
    crash_risk_score: float = 0.0
    gap_risk_score: float = 0.0
    correlation_tail_risk: float = 0.0
    overall_tail_risk: str = "MODERATE"  # LOW, MODERATE, HIGH, EXTREME
    timestamp: datetime = field(default_factory=datetime.now)


class TailRiskEngine:
    """
    Tail risk analysis engine.

    Composite tail risk score:
        score = w1 * ES_ratio + w2 * skewness + w3 * kurtosis + w4 * gap_risk

    Risk levels:
        LOW:     Normal tail behavior
        MODERATE: Slightly elevated tails
        HIGH:    Significant tail risk
        EXTREME: Critical tail risk
    """

    def __init__(self) -> None:
        self._last_metrics: Optional[TailRiskMetrics] = None

    async def analyze(
        self,
        returns: Optional[list[float]] = None,
        es_95: float = 0.05,
        es_99: float = 0.08,
        var_95: float = 0.03,
        skewness: float = -0.5,
        kurtosis: float = 3.0,
        gap_events: Optional[list[float]] = None,
        correlation_tail: float = 0.0,
    ) -> TailRiskMetrics:
        """Analyze tail risk profile."""
        metrics = TailRiskMetrics(
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            skewness=skewness,
            excess_kurtosis=kurtosis,
            correlation_tail_risk=correlation_tail,
        )

        # VaR ratio (ES/VaR) — how fat are the tails?
        metrics.var_ratio = es_95 / max(var_95, 0.0001)

        # Individual risk scores
        metrics.crash_risk_score = min(1.0, metrics.var_ratio / 3.0)

        if gap_events:
            avg_gap = sum(abs(g) for g in gap_events) / len(gap_events)
            metrics.gap_risk_score = min(1.0, avg_gap / 0.05)

        # Composite score
        composite = (
            metrics.crash_risk_score * 0.35
            + min(1.0, abs(skewness) / 2.0) * 0.20
            + min(1.0, kurtosis / 6.0) * 0.20
            + metrics.gap_risk_score * 0.15
            + min(1.0, correlation_tail) * 0.10
        )

        if composite < 0.25:
            metrics.overall_tail_risk = "LOW"
        elif composite < 0.50:
            metrics.overall_tail_risk = "MODERATE"
        elif composite < 0.75:
            metrics.overall_tail_risk = "HIGH"
        else:
            metrics.overall_tail_risk = "EXTREME"

        metrics.timestamp = datetime.now()
        self._last_metrics = metrics

        logger.info(
            "Tail risk: overall=%s crash=%.2f gap=%.2f var_ratio=%.2f",
            metrics.overall_tail_risk, metrics.crash_risk_score,
            metrics.gap_risk_score, metrics.var_ratio,
        )
        return metrics

    def compute_max_adverse_excursion(
        self, returns: list[float]
    ) -> float:
        """Compute maximum adverse excursion from the peak."""
        if not returns:
            return 0.0
        peak = 0.0
        max_excursion = 0.0
        running_pnl = 0.0
        for r in returns:
            running_pnl += r
            peak = max(peak, running_pnl)
            excursion = peak - running_pnl
            max_excursion = max(max_excursion, excursion)
        return max_excursion

    def tail_dependence(
        self, returns_a: list[float], returns_b: list[float],
        quantile: float = 0.05,
    ) -> float:
        """Estimate tail dependence coefficient between two return series."""
        if not returns_a or not returns_b or len(returns_a) != len(returns_b):
            return 0.0
        n = len(returns_a)
        cutoff = int(n * quantile)
        if cutoff < 2:
            return 0.0

        rank_a = sorted(range(n), key=lambda i: returns_a[i])
        rank_b = sorted(range(n), key=lambda i: returns_b[i])
        tail_a = set(rank_a[:cutoff])
        tail_b = set(rank_b[:cutoff])
        joint = len(tail_a & tail_b)

        return joint / cutoff if cutoff > 0 else 0.0

    @property
    def last_metrics(self) -> Optional[TailRiskMetrics]:
        return self._last_metrics
