"""
Alpha Combiner — Multi-alpha fusion engine.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Supports:
    - Momentum Alpha + Value Alpha + Quality Alpha + Volatility Alpha → Combined Alpha
    - Dynamic weight-based fusion
    - Contribution breakdown tracking
"""

from __future__ import annotations

import logging
from typing import Dict, List

from services.strategy.signal.alpha_engine import AlphaScore, CombinedAlpha

logger = logging.getLogger(__name__)


class AlphaCombiner:
    """Combines multiple alpha scores into a single combined alpha per instrument.

    The combiner uses weights from AlphaWeighting to produce a weighted sum,
    along with a contribution breakdown for explainability.
    """

    def __init__(self):
        self._combination_method: str = "weighted_sum"  # "weighted_sum" | "max" | "vote"

    # ------------------------------------------------------------------
    # Combination
    # ------------------------------------------------------------------

    async def combine(self, instrument: str, scores: List[AlphaScore]) -> CombinedAlpha:
        """Combine multiple alpha scores for a single instrument.

        Args:
            instrument: The instrument being scored.
            scores: List of alpha scores from different alpha models.

        Returns:
            A CombinedAlpha with the weighted fusion result.
        """
        if not scores:
            return CombinedAlpha(instrument=instrument, combined_score=0.0)

        if len(scores) == 1:
            s = scores[0]
            effective = s.normalized_score * s.weight * s.decay_factor * s.quality_score
            return CombinedAlpha(
                instrument=instrument,
                combined_score=effective,
                alpha_scores={s.alpha_id: s.normalized_score},
                alpha_weights={s.alpha_id: s.weight},
                contribution_breakdown={s.alpha_id: effective},
                quality=min(s.quality_score, 1.0),
            )

        if self._combination_method == "weighted_sum":
            return self._weighted_sum_combine(instrument, scores)
        elif self._combination_method == "max":
            return self._max_combine(instrument, scores)
        else:
            return self._weighted_sum_combine(instrument, scores)

    def _weighted_sum_combine(self, instrument: str, scores: List[AlphaScore]) -> CombinedAlpha:
        """Weighted sum combination."""
        alpha_scores: Dict[str, float] = {}
        alpha_weights: Dict[str, float] = {}
        contribution: Dict[str, float] = {}

        total_weight = sum(s.weight for s in scores)
        if total_weight == 0:
            total_weight = 1.0

        combined = 0.0
        total_quality = 0.0

        for s in scores:
            effective_score = s.normalized_score * s.decay_factor * s.quality_score
            norm_weight = s.weight / total_weight
            weighted_contribution = effective_score * norm_weight

            alpha_scores[s.alpha_id] = s.normalized_score
            alpha_weights[s.alpha_id] = norm_weight
            contribution[s.alpha_id] = weighted_contribution

            combined += weighted_contribution
            total_quality += s.quality_score

        avg_quality = total_quality / len(scores) if scores else 0.0

        return CombinedAlpha(
            instrument=instrument,
            combined_score=combined,
            alpha_scores=alpha_scores,
            alpha_weights=alpha_weights,
            contribution_breakdown=contribution,
            quality=avg_quality,
        )

    def _max_combine(self, instrument: str, scores: List[AlphaScore]) -> CombinedAlpha:
        """Take the maximum absolute score (direction-aware)."""
        alpha_scores = {s.alpha_id: s.normalized_score for s in scores}
        alpha_weights = {s.alpha_id: s.weight for s in scores}

        best = max(scores, key=lambda s: abs(s.normalized_score * s.weight))
        effective = best.normalized_score * best.weight * best.decay_factor * best.quality_score

        return CombinedAlpha(
            instrument=instrument,
            combined_score=effective,
            alpha_scores=alpha_scores,
            alpha_weights=alpha_weights,
            contribution_breakdown={best.alpha_id: effective},
            quality=best.quality_score,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_method(self, method: str) -> None:
        if method in ("weighted_sum", "max", "vote"):
            self._combination_method = method
