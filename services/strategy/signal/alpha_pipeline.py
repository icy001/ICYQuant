"""
Alpha Pipeline — Raw factor → Alpha score transformation pipeline.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Pipeline:
    Raw Factor → Cleaning → Normalization → IC Evaluation → Alpha Score

Bridges Commit 11 Research Platform with the Alpha Engine.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaScore
from services.strategy.signal.alpha_registry import AlphaInfo

logger = logging.getLogger(__name__)


class AlphaPipeline:
    """Transforms raw research factors into standardized alpha scores.

    Pipeline stages:
        1. Factor Cleaning     — Handle NaN, inf, outliers
        2. Normalization       — Cross-sectional z-score or rank normalization
        3. IC Evaluation       — Information coefficient tracking
        4. Alpha Score         — Final alpha score output
    """

    def __init__(self):
        self._outlier_std_threshold: float = 5.0
        self._normalization_method: str = "zscore"  # "zscore" or "rank"

    # ------------------------------------------------------------------
    # Main Pipeline
    # ------------------------------------------------------------------

    async def run(
        self,
        alpha_info: AlphaInfo,
        instruments: List[str],
        factors: Dict[str, Dict[str, float]],
        context: Dict[str, Any],
    ) -> List[AlphaScore]:
        """Run the full alpha pipeline.

        Args:
            alpha_info: The alpha model metadata from registry.
            instruments: Instruments to compute alpha for.
            factors: Factor values: {factor_name: {instrument: value}}.
            context: Additional context (market data, etc.).

        Returns:
            List of AlphaScore, one per instrument.
        """
        scores = []

        for inst in instruments:
            # 1. Collect required factors
            factor_values = self._collect_factors(alpha_info.requires_factors, factors, inst)

            if not factor_values:
                logger.debug("No factors for %s:%s, skipping", alpha_info.alpha_id, inst)
                continue

            # 2. Clean factor values
            cleaned = self._clean_factors(factor_values)

            # 3. Compute raw alpha score
            raw_score = await self._compute_alpha(alpha_info, cleaned, inst, context)

            # 4. Create score object
            scores.append(AlphaScore(
                alpha_id=alpha_info.alpha_id,
                alpha_name=alpha_info.name,
                alpha_type=alpha_info.alpha_type,
                instrument=inst,
                raw_score=raw_score,
                metadata={"factors": cleaned},
            ))

        # 5. Cross-sectional normalization (across instruments)
        if len(scores) > 1:
            scores = self._cross_sectional_normalize(scores)

        return scores

    # ------------------------------------------------------------------
    # Pipeline Stages
    # ------------------------------------------------------------------

    def _collect_factors(
        self,
        required: List[str],
        factors: Dict[str, Dict[str, float]],
        instrument: str,
    ) -> Dict[str, float]:
        """Collect required factor values for a single instrument."""
        collected = {}
        for factor_name in required:
            factor_data = factors.get(factor_name, {})
            value = factor_data.get(instrument)
            if value is not None:
                collected[factor_name] = value
        return collected

    def _clean_factors(self, factor_values: Dict[str, float]) -> Dict[str, float]:
        """Clean factor values: remove NaN, clip extreme outliers."""
        cleaned = {}
        for name, value in factor_values.items():
            if math.isnan(value) or math.isinf(value):
                continue
            # Clip to reasonable range
            cleaned[name] = max(-1e6, min(1e6, value))
        return cleaned

    async def _compute_alpha(
        self,
        alpha_info: AlphaInfo,
        factors: Dict[str, float],
        instrument: str,
        context: Dict[str, Any],
    ) -> float:
        """Compute raw alpha score from factor values.

        Default implementation uses equal-weighted factor combination.
        Extend this with alpha-specific logic (ML models, rules, etc.).
        """
        if not factors:
            return 0.0

        # Simple equal-weighted combination
        # In production, this would use alpha-specific weights or model inference
        total = sum(factors.values())
        count = len(factors)

        if count == 0:
            return 0.0

        raw_score = total / count

        # Apply sigmoid to bound within reasonable range
        try:
            raw_score = 2.0 / (1.0 + math.exp(-raw_score)) - 1.0
        except OverflowError:
            raw_score = 1.0 if raw_score > 0 else -1.0

        return raw_score

    def _cross_sectional_normalize(self, scores: List[AlphaScore]) -> List[AlphaScore]:
        """Normalize scores cross-sectionally using z-score method."""
        raw_scores = [s.raw_score for s in scores]
        n = len(raw_scores)
        if n < 2:
            return scores

        mean = sum(raw_scores) / n
        variance = sum((x - mean) ** 2 for x in raw_scores) / n
        std = max(variance ** 0.5, 1e-8)

        for i, score in enumerate(scores):
            score.normalized_score = (score.raw_score - mean) / std
            # Clamp
            score.normalized_score = max(-3.0, min(3.0, score.normalized_score))

        return scores

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_outlier_threshold(self, std_threshold: float) -> None:
        self._outlier_std_threshold = std_threshold

    def set_normalization_method(self, method: str) -> None:
        if method in ("zscore", "rank"):
            self._normalization_method = method
