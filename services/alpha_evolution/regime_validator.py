"""
Regime Validator — Validates alpha performance across market regimes.

Key regimes:
    - Bull market
    - Bear market
    - High volatility
    - Low volatility
    - Risk-on
    - Risk-off
    - Trending
    - Mean-reverting

An alpha that only works in one regime is fragile.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MARKET_REGIMES = [
    "bull", "bear", "high_vol", "low_vol",
    "risk_on", "risk_off", "trending", "mean_reverting",
]


class RegimeStatus(Enum):
    ROBUST = "robust"
    FRAGILE = "fragile"
    PARTIAL = "partial"
    NOT_TESTED = "not_tested"


@dataclass
class RegimeResult:
    individual_id: str
    status: RegimeStatus = RegimeStatus.NOT_TESTED
    regime_scores: Dict[str, float] = field(default_factory=dict)
    best_regime: str = ""
    worst_regime: str = ""
    regime_count: int = 0
    min_regime_score: float = 0.0
    overall_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


class RegimeValidator:
    """
    Validates alpha performance across market regimes.

    The alpha must be evaluated in each regime and demonstrate
    acceptable performance in the majority of regimes.
    """

    def __init__(
        self,
        min_regimes_passing: int = 5,
        min_regime_score: float = 0.10,
        min_bear_performance: float = -0.10,
    ):
        self._min_regimes_passing = min_regimes_passing
        self._min_regime_score = min_regime_score
        self._min_bear_performance = min_bear_performance

    async def validate(
        self,
        individual_id: str,
        regime_performance: Optional[Dict[str, float]] = None,
    ) -> RegimeResult:
        """Validate alpha across market regimes."""
        perf = regime_performance or {}
        result = RegimeResult(individual_id=individual_id)
        result.regime_scores = perf

        if not perf:
            result.status = RegimeStatus.NOT_TESTED
            return result

        # Count passing regimes
        passing = {
            regime: score
            for regime, score in perf.items()
            if score >= self._min_regime_score
        }
        result.regime_count = len(passing)

        # Best/worst
        if perf:
            result.best_regime = max(perf, key=lambda k: perf.get(k, -999))  # type: ignore[arg-type]
            result.worst_regime = min(perf, key=lambda k: perf.get(k, 999))  # type: ignore[arg-type]
            result.min_regime_score = min(perf.values())

        # Bear market check
        bear_score = perf.get("bear", perf.get("risk_off", 1.0))
        if bear_score < self._min_bear_performance:
            result.failure_reasons.append(
                f"Bear market score {bear_score:.3f} < {self._min_bear_performance}"
            )

        # Overall
        result.overall_score = sum(perf.values()) / max(len(perf), 1)

        if result.regime_count >= self._min_regimes_passing and not result.failure_reasons:
            result.status = RegimeStatus.ROBUST
        elif result.failure_reasons:
            result.status = RegimeStatus.FRAGILE
        else:
            result.status = RegimeStatus.PARTIAL

        return result

    async def validate_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, float]]]],
    ) -> Dict[str, RegimeResult]:
        results = {}
        for oid, perf in individuals:
            results[oid] = await self.validate(oid, perf)
        return results

    def get_regime_list(self) -> List[str]:
        return list(MARKET_REGIMES)
