"""
Signal Ranker — Priority-based ordering of trading signals.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Ranking dimensions:
    Expected Return × Confidence × (1 / Risk Score) × Liquidity × (1 / Execution Cost)

The ranker produces an ordered list for position sizing and execution priority.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.strategy.signal.signal_engine import Signal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RankDimension(str, Enum):
    """Dimensions used for signal ranking."""
    CONFIDENCE = "confidence"
    EXPECTED_RETURN = "expected_return"
    RISK_SCORE = "risk_score"
    LIQUIDITY = "liquidity"
    EXECUTION_COST = "execution_cost"
    ALPHA_QUALITY = "alpha_quality"
    TIMELINESS = "timeliness"


@dataclass
class RankedSignal:
    """A signal with its computed rank score and breakdown."""
    signal: Signal
    rank_score: float = 0.0
    rank_position: int = 0
    dimension_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class RankConfig:
    """Configuration for the ranking algorithm."""
    dimensions: Dict[RankDimension, float] = field(default_factory=lambda: {
        RankDimension.CONFIDENCE: 0.35,
        RankDimension.EXPECTED_RETURN: 0.30,
        RankDimension.RISK_SCORE: -0.15,
        RankDimension.LIQUIDITY: 0.10,
        RankDimension.ALPHA_QUALITY: 0.10,
    })
    max_ranked_signals: int = 100
    min_rank_score: float = 0.0


# ---------------------------------------------------------------------------
# Signal Ranker
# ---------------------------------------------------------------------------

class SignalRanker:
    """Prioritizes signals for execution order.

    Uses a weighted multi-dimensional scoring model. Signals are ranked by:
        Σ (dimension_score × weight)

    Higher scores = higher execution priority.
    """

    def __init__(self, config: Optional[RankConfig] = None):
        self.config = config or RankConfig()
        self._rank_history: List[RankedSignal] = []

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    async def rank(self, signals: List[Signal]) -> List[Signal]:
        """Rank signals and return them in descending priority order.

        Args:
            signals: Unordered list of validated signals.

        Returns:
            Signals sorted by rank score (highest first).
        """
        if not signals:
            return []

        ranked = []
        for sig in signals:
            score, dim_scores = await self._compute_rank_score(sig)
            if score >= self.config.min_rank_score:
                ranked.append(RankedSignal(
                    signal=sig,
                    rank_score=score,
                    dimension_scores=dim_scores,
                ))

        # Sort by score descending
        ranked.sort(key=lambda r: r.rank_score, reverse=True)

        # Assign positions
        for i, rs in enumerate(ranked[:self.config.max_ranked_signals]):
            rs.rank_position = i + 1

        # Store history
        self._rank_history = ranked[:self.config.max_ranked_signals]

        result = [rs.signal for rs in ranked[:self.config.max_ranked_signals]]

        if len(signals) > len(result):
            logger.debug("Ranked %d/%d signals (min_score=%.2f)",
                         len(result), len(signals), self.config.min_rank_score)

        return result

    async def _compute_rank_score(self, signal: Signal) -> Tuple[float, Dict[str, float]]:
        """Compute the composite rank score for a single signal."""
        dim_scores: Dict[str, float] = {}

        # Confidence (0-1)
        confidence = signal.confidence
        dim_scores[RankDimension.CONFIDENCE.value] = confidence

        # Expected return (from alpha scores or metadata)
        expected_return = signal.metadata.get("expected_return", 0.0)
        # Normalize to ~[0,1] via sigmoid
        import math
        try:
            er_norm = 1.0 / (1.0 + math.exp(-expected_return * 5))
        except OverflowError:
            er_norm = 1.0 if expected_return > 0 else 0.0
        dim_scores[RankDimension.EXPECTED_RETURN.value] = er_norm

        # Risk score (lower is better, so we invert)
        risk_score = signal.metadata.get("risk_score", 0.5)
        risk_inverted = 1.0 - min(risk_score, 1.0)
        dim_scores[RankDimension.RISK_SCORE.value] = risk_inverted

        # Liquidity (0-1, from metadata or default)
        liquidity = signal.metadata.get("liquidity_score", 0.5)
        dim_scores[RankDimension.LIQUIDITY.value] = liquidity

        # Alpha quality (average of alpha scores)
        alpha_scores = signal.alpha_scores
        if alpha_scores:
            alpha_quality = sum(alpha_scores.values()) / len(alpha_scores)
            alpha_quality = max(0.0, min(1.0, alpha_quality))
        else:
            alpha_quality = 0.5
        dim_scores[RankDimension.ALPHA_QUALITY.value] = alpha_quality

        # Weighted sum
        total = 0.0
        total_weight = 0.0
        for dim, weight in self.config.dimensions.items():
            score = dim_scores.get(dim.value, 0.0)
            if weight >= 0:
                total += score * weight
                total_weight += weight
            else:
                # Negative weight means penalty (e.g., risk)
                total += score * weight
                total_weight += abs(weight)

        # Normalize
        if total_weight > 0:
            total = total / total_weight

        # Clamp to [0, 1]
        total = max(0.0, min(1.0, total))

        return total, dim_scores

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_rank_history(self, limit: int = 50) -> List[RankedSignal]:
        """Get the most recent ranking results."""
        return self._rank_history[-limit:]

    def get_top_signals(self, n: int = 10) -> List[Signal]:
        """Get the top N signals from the last ranking."""
        return [rs.signal for rs in self._rank_history[:n]]

    def update_weights(self, dimensions: Dict[RankDimension, float]) -> None:
        """Update dimension weights."""
        self.config.dimensions.update(dimensions)
        logger.info("Updated ranking weights: %s", self.config.dimensions)
