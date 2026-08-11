"""
Fitness Function — Multi-dimensional fitness scoring for factor/alpha candidates.

Fitness dimensions:
    - IC (Information Coefficient)
    - Rank IC
    - Sharpe Ratio
    - Sortino Ratio
    - Stability (IC stability over time)
    - Robustness (OOS performance retention)
    - Capacity (max AUM estimate)
    - Turnover (lower is better)
    - Max Drawdown (lower is better)
    - Win Rate
    - Profit Factor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FitnessDimension(Enum):
    IC = "ic"
    RANK_IC = "rank_ic"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    STABILITY = "stability"
    ROBUSTNESS = "robustness"
    CAPACITY = "capacity"
    TURNOVER = "turnover"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    NOVELTY = "novelty"
    DIVERSITY = "diversity"


@dataclass
class FitnessWeights:
    """Default weights for fitness dimensions."""

    ic: float = 0.15
    rank_ic: float = 0.10
    sharpe: float = 0.15
    sortino: float = 0.05
    stability: float = 0.10
    robustness: float = 0.10
    capacity: float = 0.10
    turnover: float = -0.05  # negative = minimize
    max_drawdown: float = -0.05
    win_rate: float = 0.05
    profit_factor: float = 0.05
    novelty: float = 0.10
    diversity: float = 0.05

    def to_dict(self) -> Dict[str, float]:
        return {
            "ic": self.ic,
            "rank_ic": self.rank_ic,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "stability": self.stability,
            "robustness": self.robustness,
            "capacity": self.capacity,
            "turnover": self.turnover,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "novelty": self.novelty,
            "diversity": self.diversity,
        }


@dataclass
class FitnessScore:
    """Multi-dimensional fitness score for one individual."""

    individual_id: str
    ic: float = 0.0
    rank_ic: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    stability: float = 0.0
    robustness: float = 0.0
    capacity: float = 0.0
    turnover: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    novelty: float = 0.0
    diversity: float = 0.0
    composite: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_composite(self, weights: Optional[FitnessWeights] = None) -> float:
        """Compute weighted composite fitness."""
        w = weights or FitnessWeights()
        self.composite = (
            self.ic * w.ic
            + self.rank_ic * w.rank_ic
            + self.sharpe * w.sharpe
            + self.sortino * w.sortino
            + self.stability * w.stability
            + self.robustness * w.robustness
            + self.capacity * w.capacity
            + self.turnover * w.turnover
            + self.max_drawdown * w.max_drawdown
            + self.win_rate * w.win_rate
            + self.profit_factor * w.profit_factor
            + self.novelty * w.novelty
            + self.diversity * w.diversity
        )
        return self.composite

    def to_dict(self) -> Dict[str, float]:
        return {
            "ic": self.ic,
            "rank_ic": self.rank_ic,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "stability": self.stability,
            "robustness": self.robustness,
            "capacity": self.capacity,
            "turnover": self.turnover,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "novelty": self.novelty,
            "diversity": self.diversity,
            "composite": self.composite,
        }


class FitnessFunction:
    """
    Multi-dimensional fitness scoring system.

    Evaluates factor/alpha candidates across 13 dimensions:
        IC ↑, Rank IC ↑, Sharpe ↑, Sortino ↑, Stability ↑,
        Robustness ↑, Capacity ↑, Turnover ↓, Max DD ↓,
        Win Rate ↑, Profit Factor ↑, Novelty ↑, Diversity ↑
    """

    def __init__(self, weights: Optional[FitnessWeights] = None):
        self._weights = weights or FitnessWeights()

    def score(
        self,
        individual_id: str,
        metrics: Dict[str, float],
        novelty: float = 0.0,
        diversity: float = 0.0,
    ) -> FitnessScore:
        """
        Compute multi-dimensional fitness from raw metrics.

        Args:
            individual_id: Individual identifier
            metrics: Dict of metric name → value
            novelty: External novelty score
            diversity: External diversity contribution

        Returns:
            FitnessScore with composite
        """
        score = FitnessScore(
            individual_id=individual_id,
            ic=metrics.get("ic", 0),
            rank_ic=metrics.get("rank_ic", 0),
            sharpe=metrics.get("sharpe", 0),
            sortino=metrics.get("sortino", 0),
            stability=metrics.get("stability", 0),
            robustness=metrics.get("robustness", 0),
            capacity=metrics.get("capacity", 0),
            turnover=metrics.get("turnover", 0),
            max_drawdown=metrics.get("max_drawdown", 0),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 0),
            novelty=novelty,
            diversity=diversity,
        )
        score.compute_composite(self._weights)
        return score

    def score_batch(
        self,
        individuals: List[Dict[str, Any]],
        novelty_map: Optional[Dict[str, float]] = None,
        diversity_map: Optional[Dict[str, float]] = None,
    ) -> List[FitnessScore]:
        """Score multiple individuals in batch."""
        results = []
        for ind in individuals:
            oid = ind.get("id", "")
            metrics = ind.get("metrics", {})
            novelty = (novelty_map or {}).get(oid, 0)
            diversity = (diversity_map or {}).get(oid, 0)
            results.append(self.score(oid, metrics, novelty, diversity))
        return results

    def normalize_scores(
        self, scores: List[FitnessScore]
    ) -> List[FitnessScore]:
        """Normalize composite scores to [0, 1] range."""
        if not scores:
            return scores
        composites = [s.composite for s in scores]
        min_val = min(composites)
        max_val = max(composites)
        if max_val == min_val:
            return scores
        for s in scores:
            s.composite = (s.composite - min_val) / (max_val - min_val)
        return scores

    def get_dimension_weight(self, dim: FitnessDimension) -> float:
        """Get the weight for a fitness dimension."""
        attr = dim.value
        return getattr(self._weights, attr, 0)
