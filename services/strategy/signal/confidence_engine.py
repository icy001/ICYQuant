"""
Confidence Engine — Multi-dimensional confidence scoring for signals.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Confidence = Alpha Score + Factor Quality + Backtest Score + Market Regime

Low confidence signals are automatically down-weighted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of confidence score components."""
    signal_id: str = ""
    total_confidence: float = 0.0

    alpha_score_contrib: float = 0.0
    factor_quality_contrib: float = 0.0
    backtest_score_contrib: float = 0.0
    market_regime_contrib: float = 0.0
    signal_consistency_contrib: float = 0.0

    weights: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Confidence Engine
# ---------------------------------------------------------------------------

class ConfidenceEngine:
    """Computes multi-dimensional confidence scores for trading signals.

    Confidence ∈ [0, 1] where:
        - 0.0 = no confidence (should be discarded)
        - 0.5 = neutral
        - 1.0 = maximum confidence

    Dimensions:
        1. Alpha Score Quality  (40%) — How strong/reliable are the alpha signals?
        2. Factor Quality        (25%) — How clean are the underlying factors?
        3. Backtest Performance  (20%) — Historical performance of this signal type?
        4. Market Regime Fit     (15%) — Is this signal suitable for current market?
    """

    def __init__(self):
        self._weights = {
            "alpha_score": 0.40,
            "factor_quality": 0.25,
            "backtest": 0.20,
            "market_regime": 0.15,
        }

        # Backtest performance cache: strategy_id → score
        self._backtest_scores: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Confidence Scoring
    # ------------------------------------------------------------------

    async def score(self, signal: Signal) -> float:
        """Compute the confidence score for a signal.

        Returns a float in [0, 1].
        """
        breakdown = await self._compute_breakdown(signal)
        signal.metadata["confidence_breakdown"] = {
            "total": breakdown.total_confidence,
            "alpha_score_contrib": breakdown.alpha_score_contrib,
            "factor_quality_contrib": breakdown.factor_quality_contrib,
            "backtest_score_contrib": breakdown.backtest_score_contrib,
            "market_regime_contrib": breakdown.market_regime_contrib,
            "signal_consistency_contrib": breakdown.signal_consistency_contrib,
        }
        return breakdown.total_confidence

    async def _compute_breakdown(self, signal: Signal) -> ConfidenceBreakdown:
        """Compute the full confidence breakdown."""
        bd = ConfidenceBreakdown(signal_id=signal.signal_id)

        # 1. Alpha Score Quality (40%)
        bd.alpha_score_contrib = self._compute_alpha_quality(signal)

        # 2. Factor Quality (25%)
        bd.factor_quality_contrib = self._compute_factor_quality(signal)

        # 3. Backtest Performance (20%)
        bd.backtest_score_contrib = self._compute_backtest_score(signal)

        # 4. Market Regime Fit (15%)
        bd.market_regime_contrib = self._compute_regime_fit(signal)

        # Weighted combination
        bd.total_confidence = (
            self._weights["alpha_score"] * bd.alpha_score_contrib
            + self._weights["factor_quality"] * bd.factor_quality_contrib
            + self._weights["backtest"] * bd.backtest_score_contrib
            + self._weights["market_regime"] * bd.market_regime_contrib
        )

        # Clamp
        bd.total_confidence = max(0.0, min(1.0, bd.total_confidence))
        bd.weights = dict(self._weights)

        return bd

    # ------------------------------------------------------------------
    # Dimension Computations
    # ------------------------------------------------------------------

    def _compute_alpha_quality(self, signal: Signal) -> float:
        """Compute alpha score quality contribution.

        Based on the consistency and magnitude of alpha scores.
        """
        alpha_scores = signal.alpha_scores
        if not alpha_scores:
            return 0.3

        values = list(alpha_scores.values())
        if not values:
            return 0.3

        # Average absolute alpha
        avg_abs = sum(abs(v) for v in values) / len(values)
        # Normalize: 0.0 → 0.0, 1.0 → 0.8, 2.0 → 1.0
        alpha_quality = min(avg_abs / 2.0, 1.0)

        # Consistency bonus: if all alphas agree on direction
        signs = [1 if v > 0 else -1 if v < 0 else 0 for v in values]
        if len(set(signs)) == 1 and signs[0] != 0:
            alpha_quality = min(alpha_quality + 0.1, 1.0)

        return alpha_quality

    def _compute_factor_quality(self, signal: Signal) -> float:
        """Compute factor quality contribution.

        Based on factor coverage and signal-to-noise ratio from metadata.
        """
        contributions = signal.factor_contributions
        if not contributions:
            return 0.5

        # Number of contributing factors
        n_factors = len(contributions)
        # Average contribution magnitude
        avg_contrib = sum(abs(v) for v in contributions.values()) / n_factors

        # Quality = coverage × magnitude
        coverage = min(n_factors / 10.0, 1.0)  # Assuming 10+ factors is good coverage
        magnitude = min(avg_contrib, 1.0)

        return 0.5 * coverage + 0.5 * magnitude

    def _compute_backtest_score(self, signal: Signal) -> float:
        """Compute backtest performance contribution.

        Uses cached backtest scores per strategy.
        """
        score = self._backtest_scores.get(signal.strategy_id, 0.5)
        return score

    def _compute_regime_fit(self, signal: Signal) -> float:
        """Compute market regime alignment contribution.

        Based on whether the signal's regime matches current market.
        """
        regime = signal.market_regime
        if not regime:
            return 0.5  # Unknown → neutral

        # If signal has a regime tag, check if it matches common patterns
        # For now, return a default based on signal metadata
        regime_score = signal.metadata.get("regime_score", 0.5)
        return regime_score

    # ------------------------------------------------------------------
    # Backtest Score Cache
    # ------------------------------------------------------------------

    def set_backtest_score(self, strategy_id: str, score: float) -> None:
        """Cache a backtest performance score for a strategy."""
        self._backtest_scores[strategy_id] = max(0.0, min(1.0, score))

    def get_backtest_score(self, strategy_id: str) -> float:
        return self._backtest_scores.get(strategy_id, 0.5)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_weights(self, alpha_score: float, factor_quality: float,
                    backtest: float, market_regime: float) -> None:
        """Update confidence dimension weights. Must sum to 1.0."""
        total = alpha_score + factor_quality + backtest + market_regime
        self._weights = {
            "alpha_score": alpha_score / total,
            "factor_quality": factor_quality / total,
            "backtest": backtest / total,
            "market_regime": market_regime / total,
        }

    def get_breakdown(self, signal: Signal) -> Optional[Dict[str, Any]]:
        """Get the confidence breakdown from a signal's metadata."""
        return signal.metadata.get("confidence_breakdown")
