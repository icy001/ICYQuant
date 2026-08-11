"""
Alpha Weighting — Dynamic weight assignment for alpha models.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Supports:
    - Equal Weight
    - IC Weight (Information Coefficient)
    - IR Weight (Information Ratio)
    - Adaptive Weight (market regime aware)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WeightingMethod(str, Enum):
    EQUAL = "equal"
    IC_WEIGHTED = "ic_weighted"
    IR_WEIGHTED = "ir_weighted"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Alpha Weighting
# ---------------------------------------------------------------------------

class AlphaWeighting:
    """Assigns weights to alpha scores for combination.

    Each weighting method produces a normalized weight vector across alphas.
    """

    def __init__(self, method: WeightingMethod = WeightingMethod.EQUAL):
        self.method = method
        self._ic_cache: Dict[str, float] = {}  # alpha_id → IC
        self._ir_cache: Dict[str, float] = {}  # alpha_id → IR
        self._custom_weights: Dict[str, float] = {}  # alpha_id → weight

    # ------------------------------------------------------------------
    # Weight Application
    # ------------------------------------------------------------------

    async def apply_weights(self, scores: List[AlphaScore]) -> List[AlphaScore]:
        """Apply the configured weighting method to a list of alpha scores."""
        if not scores:
            return scores

        weights = await self._compute_weights(scores)
        for score in scores:
            score.weight = weights.get(score.alpha_id, 1.0 / max(len(scores), 1))

        return scores

    async def _compute_weights(self, scores: List[AlphaScore]) -> Dict[str, float]:
        """Compute weight vector based on the configured method."""
        alpha_ids = list(set(s.alpha_id for s in scores))
        n = len(alpha_ids)
        if n == 0:
            return {}

        if self.method == WeightingMethod.EQUAL:
            return self._equal_weight(alpha_ids, n)

        elif self.method == WeightingMethod.IC_WEIGHTED:
            return self._ic_weight(alpha_ids, n)

        elif self.method == WeightingMethod.IR_WEIGHTED:
            return self._ir_weight(alpha_ids, n)

        elif self.method == WeightingMethod.ADAPTIVE:
            return self._adaptive_weight(scores, alpha_ids, n)

        elif self.method == WeightingMethod.CUSTOM:
            return self._custom_weight(alpha_ids, n)

        return self._equal_weight(alpha_ids, n)

    # ------------------------------------------------------------------
    # Weighting Methods
    # ------------------------------------------------------------------

    def _equal_weight(self, alpha_ids: List[str], n: int) -> Dict[str, float]:
        """Equal weight: 1/n per alpha."""
        w = 1.0 / n
        return {aid: w for aid in alpha_ids}

    def _ic_weight(self, alpha_ids: List[str], n: int) -> Dict[str, float]:
        """IC-weighted: weight proportional to absolute IC."""
        weights = {}
        for aid in alpha_ids:
            ic = abs(self._ic_cache.get(aid, 0.05))
            weights[aid] = max(ic, 0.01)

        total = sum(weights.values())
        if total > 0:
            for aid in weights:
                weights[aid] /= total
        else:
            return self._equal_weight(alpha_ids, n)

        return weights

    def _ir_weight(self, alpha_ids: List[str], n: int) -> Dict[str, float]:
        """IR-weighted: weight proportional to Information Ratio."""
        weights = {}
        for aid in alpha_ids:
            ir = max(self._ir_cache.get(aid, 0.1), 0.01)
            weights[aid] = ir

        total = sum(weights.values())
        if total > 0:
            for aid in weights:
                weights[aid] /= total
        else:
            return self._equal_weight(alpha_ids, n)

        return weights

    def _adaptive_weight(self, scores: List[AlphaScore],
                         alpha_ids: List[str], n: int) -> Dict[str, float]:
        """Adaptive weight: blends IC and recent performance."""
        weights = {}
        for aid in alpha_ids:
            ic = abs(self._ic_cache.get(aid, 0.05))
            # Recent quality from scores
            aid_scores = [s for s in scores if s.alpha_id == aid]
            avg_quality = sum(s.quality_score for s in aid_scores) / max(len(aid_scores), 1)
            # Blend: 60% IC, 40% recent quality
            weights[aid] = 0.6 * ic + 0.4 * avg_quality

        total = sum(weights.values())
        if total > 0:
            for aid in weights:
                weights[aid] /= total
        else:
            return self._equal_weight(alpha_ids, n)

        return weights

    def _custom_weight(self, alpha_ids: List[str], n: int) -> Dict[str, float]:
        """Use pre-configured custom weights."""
        weights = {}
        for aid in alpha_ids:
            weights[aid] = self._custom_weights.get(aid, 1.0 / n)

        total = sum(weights.values())
        if total > 0:
            for aid in weights:
                weights[aid] /= total
        else:
            return self._equal_weight(alpha_ids, n)

        return weights

    # ------------------------------------------------------------------
    # Cache Updates
    # ------------------------------------------------------------------

    def update_ic(self, alpha_id: str, ic: float) -> None:
        """Update the IC cache for an alpha."""
        self._ic_cache[alpha_id] = ic

    def update_ir(self, alpha_id: str, ir: float) -> None:
        """Update the IR cache for an alpha."""
        self._ir_cache[alpha_id] = ir

    def set_custom_weights(self, weights: Dict[str, float]) -> None:
        """Set custom weights for alphas."""
        self._custom_weights.update(weights)

    def set_method(self, method: WeightingMethod) -> None:
        self.method = method
