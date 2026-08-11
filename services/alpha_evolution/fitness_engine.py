"""
Fitness Engine — Evaluates multi-dimensional fitness for all individuals.

Orchestrates:
    - Batch fitness computation
    - Metric aggregation from validation results
    - Composite scoring with configurable weights
    - Ranking and filtering by fitness
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.alpha_evolution.fitness_function import (
    FitnessFunction,
    FitnessScore,
    FitnessWeights,
    FitnessDimension,
)

logger = logging.getLogger(__name__)


class FitnessEngine:
    """
    Orchestrates multi-dimensional fitness evaluation across the population.

    Pipeline:
        Individual → Metric Extraction → FitnessScore → Composite → Ranking
    """

    def __init__(self, weights: Optional[FitnessWeights] = None):
        self._function = FitnessFunction(weights)
        self._scores: Dict[str, FitnessScore] = {}
        self._weights = weights or FitnessWeights()

    # ── Evaluation ─────────────────────────────────────────

    async def evaluate(
        self,
        individuals: List[Dict[str, Any]],
        novelty_map: Optional[Dict[str, float]] = None,
        diversity_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, FitnessScore]:
        """
        Compute fitness scores for a batch of individuals.

        Args:
            individuals: List of individual dicts with 'id' and metrics
            novelty_map: Individual ID → novelty score
            diversity_map: Individual ID → diversity score

        Returns:
            Dict of individual_id → FitnessScore
        """
        scores = self._function.score_batch(
            individuals, novelty_map, diversity_map
        )
        self._scores = {s.individual_id: s for s in scores}
        logger.debug("Evaluated fitness for %d individuals", len(scores))
        return self._scores

    async def evaluate_single(
        self,
        individual_id: str,
        metrics: Dict[str, float],
        novelty: float = 0.0,
        diversity: float = 0.0,
    ) -> FitnessScore:
        """Compute fitness for a single individual."""
        score = self._function.score(individual_id, metrics, novelty, diversity)
        self._scores[individual_id] = score
        return score

    # ── Ranking ────────────────────────────────────────────

    def rank_by_composite(
        self, individual_ids: Optional[List[str]] = None, descending: bool = True
    ) -> List[tuple[str, float]]:
        """Rank individuals by composite fitness."""
        if individual_ids:
            pairs = [
                (oid, self._scores.get(oid, FitnessScore(individual_id=oid)).composite)
                for oid in individual_ids
            ]
        else:
            pairs = [(oid, s.composite) for oid, s in self._scores.items()]
        pairs.sort(key=lambda x: x[1], reverse=descending)
        return pairs

    def rank_by_dimension(
        self, dim: FitnessDimension, descending: bool = True
    ) -> List[tuple[str, float]]:
        """Rank individuals by a specific fitness dimension."""
        pairs = []
        for oid, score in self._scores.items():
            value = getattr(score, dim.value, 0)
            pairs.append((oid, value))
        pairs.sort(key=lambda x: x[1], reverse=descending)
        return pairs

    def get_top_n(self, n: int = 10) -> List[str]:
        """Get IDs of top N individuals by composite fitness."""
        ranked = self.rank_by_composite()
        return [oid for oid, _ in ranked[:n]]

    def filter_above_threshold(self, min_fitness: float) -> List[str]:
        """Get IDs of individuals above a fitness threshold."""
        return [
            oid for oid, s in self._scores.items()
            if s.composite >= min_fitness
        ]

    # ── Statistics ─────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Compute population fitness statistics."""
        if not self._scores:
            return {"count": 0}

        composites = [s.composite for s in self._scores.values()]
        ics = [s.ic for s in self._scores.values()]
        sharpes = [s.sharpe for s in self._scores.values()]

        composites.sort()
        n = len(composites)

        return {
            "count": n,
            "composite": {
                "mean": sum(composites) / n,
                "max": max(composites),
                "min": min(composites),
                "median": composites[n // 2] if n > 0 else 0,
            },
            "ic": {
                "mean": sum(ics) / n,
                "max": max(ics),
            },
            "sharpe": {
                "mean": sum(sharpes) / n,
                "max": max(sharpes),
            },
        }

    def get_score(self, individual_id: str) -> Optional[FitnessScore]:
        """Get fitness score for an individual."""
        return self._scores.get(individual_id)

    def get_all_scores(self) -> Dict[str, FitnessScore]:
        """Get all fitness scores."""
        return dict(self._scores)

    def clear(self) -> None:
        """Clear all scores."""
        self._scores.clear()
