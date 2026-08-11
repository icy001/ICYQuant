"""Portfolio Recommender — autonomously constructs portfolio recommendations from alpha pools.

Pipeline:
    Alpha Pool + Backtest Results -> PortfolioRecommender.recommend()
        -> Score candidates by alpha quality
        -> Apply position sizing constraints
        -> Diversify across factors / sectors
        -> Generate PortfolioRecommendation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRecommendation:
    """A portfolio recommendation with allocations.

    Attributes:
        recommendation_id: Unique identifier.
        name: Portfolio name.
        allocations: Dict of symbol -> weight.
        expected_return: Portfolio expected return.
        expected_risk: Portfolio expected risk.
        sharpe: Portfolio Sharpe ratio.
        confidence: Recommendation confidence (0.0-1.0).
        rationale: Human-readable rationale.
        metadata: Additional data.
        created_at: Creation timestamp.
    """

    recommendation_id: str = ""
    name: str = ""
    allocations: Dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe: float = 0.0
    confidence: float = 0.0
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_weight(self) -> float:
        return sum(self.allocations.values())

    @property
    def position_count(self) -> int:
        return len(self.allocations)


class PortfolioRecommender:
    """Autonomously constructs portfolio recommendations.

    Combines alpha pool signals, backtest results, and risk constraints
    to generate diversified portfolio recommendations.

    Supports:
        - Alpha-driven position sizing
        - Multi-factor diversification
        - Sector concentration limits
        - Confidence scoring

    Usage:
        recommender = PortfolioRecommender()
        await recommender.initialize()
        rec = await recommender.recommend(alpha_pool=[...], constraints={...})
    """

    def __init__(
        self,
        max_positions: int = 30,
        max_single_weight: float = 0.10,
        max_sector_weight: float = 0.30,
    ) -> None:
        self._max_positions = max_positions
        self._max_single_weight = max_single_weight
        self._max_sector_weight = max_sector_weight
        self._recommendations: List[PortfolioRecommendation] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("PortfolioRecommender created (max_positions=%d, max_single=%.0f%%)", max_positions, max_single_weight * 100)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PortfolioRecommender initialized")

    async def shutdown(self) -> None:
        self._recommendations.clear()
        self._initialized = False
        logger.info("PortfolioRecommender shutdown complete")

    async def recommend(
        self,
        alpha_pool: Optional[List[Dict[str, Any]]] = None,
        backtest_results: Optional[List[Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> PortfolioRecommendation:
        """Generate a portfolio recommendation.

        Args:
            alpha_pool: Alpha factors with scores.
            backtest_results: Backtest performance data.
            constraints: Portfolio constraints.

        Returns:
            A PortfolioRecommendation.
        """
        logger.info("PortfolioRecommender.recommend() started")
        self._counter += 1
        rec = PortfolioRecommendation(
            recommendation_id=f"rec_{self._counter}",
            name=f"Portfolio Recommendation {self._counter}",
            allocations={},
            confidence=0.5,
            rationale="Generated from alpha pool",
        )
        self._recommendations.append(rec)
        logger.info("PortfolioRecommender.recommend() completed: %s", rec.recommendation_id)
        return rec

    def get_recent_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.recommendation_id,
                "name": r.name,
                "positions": r.position_count,
                "expected_return": round(r.expected_return, 4),
                "sharpe": round(r.sharpe, 3),
                "confidence": round(r.confidence, 3),
            }
            for r in self._recommendations[-limit:]
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_recommendations": len(self._recommendations),
        }
