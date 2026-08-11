"""
Liquidity Score — Composite 0-100 score for tradable assets.

Synthesizes: Volume, Depth, Spread, Volatility, Turnover, Execution History
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LiquidityScore:
    """Composite liquidity assessment 0-100."""

    score_id: str = field(default_factory=lambda: f"LS-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    overall_score: float = 50.0

    # Sub-scores (0-100)
    volume_score: float = 50.0
    spread_score: float = 50.0
    depth_score: float = 50.0
    volatility_score: float = 50.0
    turnover_score: float = 50.0

    # Weights
    volume_weight: float = 0.30
    spread_weight: float = 0.25
    depth_weight: float = 0.20
    volatility_weight: float = 0.15
    turnover_weight: float = 0.10

    def compute_overall(self) -> float:
        self.overall_score = (
            self.volume_score * self.volume_weight +
            self.spread_score * self.spread_weight +
            self.depth_score * self.depth_weight +
            self.volatility_score * self.volatility_weight +
            self.turnover_score * self.turnover_weight
        )
        return self.overall_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_id": self.score_id,
            "asset": self.asset,
            "overall": self.overall_score,
            "volume": self.volume_score,
            "spread": self.spread_score,
            "depth": self.depth_score,
            "volatility": self.volatility_score,
            "turnover": self.turnover_score,
        }

    @property
    def tier(self) -> str:
        if self.overall_score >= 85:
            return "EXCELLENT"
        elif self.overall_score >= 70:
            return "GOOD"
        elif self.overall_score >= 50:
            return "ADEQUATE"
        elif self.overall_score >= 30:
            return "POOR"
        return "CRITICAL"


class LiquidityScorer:
    """Scores asset liquidity on a 0-100 scale."""

    @staticmethod
    def _score_volume(notional: float) -> float:
        if notional > 1_000_000_000:
            return 95.0
        elif notional > 500_000_000:
            return 85.0
        elif notional > 100_000_000:
            return 70.0
        elif notional > 10_000_000:
            return 50.0
        elif notional > 1_000_000:
            return 30.0
        else:
            return 10.0

    @staticmethod
    def _score_spread(spread_bps: float) -> float:
        if spread_bps <= 1:
            return 95.0
        elif spread_bps <= 5:
            return 80.0
        elif spread_bps <= 20:
            return 60.0
        elif spread_bps <= 50:
            return 40.0
        elif spread_bps <= 100:
            return 20.0
        else:
            return 5.0

    @staticmethod
    def _score_depth(depth_notional: float) -> float:
        if depth_notional > 10_000_000:
            return 90.0
        elif depth_notional > 1_000_000:
            return 70.0
        elif depth_notional > 100_000:
            return 50.0
        elif depth_notional > 10_000:
            return 30.0
        return 10.0

    @staticmethod
    def _score_volatility(vol: float) -> float:
        if vol <= 0.10:
            return 90.0
        elif vol <= 0.20:
            return 75.0
        elif vol <= 0.35:
            return 55.0
        elif vol <= 0.50:
            return 35.0
        return 15.0

    @staticmethod
    def _score_turnover(turnover: float) -> float:
        if turnover > 5.0:
            return 90.0
        elif turnover > 2.0:
            return 70.0
        elif turnover > 1.0:
            return 50.0
        elif turnover > 0.3:
            return 30.0
        return 10.0

    def score(
        self, asset: str,
        avg_daily_notional: float = 0.0,
        avg_spread_bps: float = 0.0,
        book_depth: float = 0.0,
        volatility: float = 0.0,
        turnover: float = 0.0,
    ) -> LiquidityScore:
        s = LiquidityScore(
            asset=asset,
            volume_score=self._score_volume(avg_daily_notional),
            spread_score=self._score_spread(avg_spread_bps),
            depth_score=self._score_depth(book_depth),
            volatility_score=self._score_volatility(volatility),
            turnover_score=self._score_turnover(turnover),
        )
        s.compute_overall()
        return s

    def batch_score(self, assets: List[Tuple[str, float, float, float, float, float]]) -> List[LiquidityScore]:
        return [self.score(a, n, s, d, v, t) for a, n, s, d, v, t in assets]
