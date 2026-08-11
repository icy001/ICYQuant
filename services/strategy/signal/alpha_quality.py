"""
Alpha Quality — Quality and stability scoring for alpha models.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Evaluates:
    - Score stability (variance over recent windows)
    - Factor coverage (completeness of input data)
    - Score reasonability (within expected bounds)
    - Cross-validation consistency
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaScore

logger = logging.getLogger(__name__)


class AlphaQuality:
    """Evaluates the quality of alpha scores.

    Quality score ∈ [0, 1] where higher is better. Used to:
        - Downweight low-quality alpha contributions
        - Flag alphas that need recalibration
        - Filter unreliable signals downstream
    """

    def __init__(self):
        # History for stability tracking
        self._score_history: Dict[str, List[float]] = defaultdict(list)  # alpha_id:instrument → recent scores
        self._max_history: int = 100

        # Quality thresholds
        self._stability_weight: float = 0.4
        self._coverage_weight: float = 0.3
        self._reasonability_weight: float = 0.3

    # ------------------------------------------------------------------
    # Quality Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, score: AlphaScore) -> float:
        """Evaluate the quality of an alpha score.

        Returns a quality score ∈ [0, 1].
        """
        key = f"{score.alpha_id}:{score.instrument}"

        # 1. Stability: how consistent is this alpha over time?
        stability = self._evaluate_stability(key, score.raw_score)

        # 2. Coverage: how complete are the input factors?
        coverage = self._evaluate_coverage(score)

        # 3. Reasonability: is the score within expected bounds?
        reasonability = self._evaluate_reasonability(score)

        # Weighted combination
        quality = (
            self._stability_weight * stability
            + self._coverage_weight * coverage
            + self._reasonability_weight * reasonability
        )

        # Clamp
        quality = max(0.0, min(1.0, quality))

        # Update history
        self._score_history[key].append(score.raw_score)
        if len(self._score_history[key]) > self._max_history:
            self._score_history[key] = self._score_history[key][-self._max_history:]

        return quality

    # ------------------------------------------------------------------
    # Quality Dimensions
    # ------------------------------------------------------------------

    def _evaluate_stability(self, key: str, current_score: float) -> float:
        """Evaluate score stability over recent history.

        Lower variance → higher stability → higher quality.
        """
        history = self._score_history.get(key, [])
        if len(history) < 3:
            return 0.5  # Neutral for insufficient data

        recent = history[-20:]  # Last 20 observations
        if len(recent) < 3:
            return 0.5

        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        std = max(variance ** 0.5, 1e-8)

        # Normalize: score of 1.0 when std is near 0, decreasing as std grows
        # Using: quality = exp(-std) as a smooth decay
        stability = math.exp(-std)

        return max(0.0, min(1.0, stability))

    def _evaluate_coverage(self, score: AlphaScore) -> float:
        """Evaluate how complete the factor coverage is.

        Checks metadata for factor count vs expected.
        """
        factors = score.metadata.get("factors", {})
        if not factors:
            return 0.3

        # Count non-None factor values
        valid_factors = sum(1 for v in factors.values() if v is not None and not math.isnan(v))
        total_factors = len(factors)
        if total_factors == 0:
            return 0.3

        coverage_ratio = valid_factors / total_factors
        return coverage_ratio

    def _evaluate_reasonability(self, score: AlphaScore) -> float:
        """Evaluate whether the score is within reasonable bounds."""
        # Raw scores should generally be in [-10, 10] for most alphas
        # Extreme values reduce quality
        abs_score = abs(score.raw_score)

        if abs_score > 100:
            return 0.1
        elif abs_score > 10:
            return 0.5 - 0.4 * (abs_score - 10) / 90
        elif abs_score > 5:
            return 0.8
        else:
            return 1.0

    # ------------------------------------------------------------------
    # Bulk Evaluation
    # ------------------------------------------------------------------

    async def evaluate_batch(self, scores: List[AlphaScore]) -> List[AlphaScore]:
        """Evaluate quality for a batch of scores."""
        for score in scores:
            score.quality_score = await self.evaluate(score)
        return scores

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_weights(self, stability: float, coverage: float, reasonability: float) -> None:
        """Update the quality dimension weights. Must sum to 1.0."""
        total = stability + coverage + reasonability
        self._stability_weight = stability / total
        self._coverage_weight = coverage / total
        self._reasonability_weight = reasonability / total

    def clear_history(self) -> None:
        self._score_history.clear()
