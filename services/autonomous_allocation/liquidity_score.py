"""Liquidity Score — scores strategy liquidity quality for allocation.

Evaluates how easily capital can be deployed/redeemed:
- Asset-level liquidity composite
- Market depth
- Spread width
- Volume adequacy
- Turnover velocity
- Liquidity regime impact
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityTier(str, Enum):
    """Liquidity tiers affecting allocation sizing."""
    ULTRA_LIQUID = "ULTRA_LIQUID"
    HIGHLY_LIQUID = "HIGHLY_LIQUID"
    LIQUID = "LIQUID"
    MODERATE = "MODERATE"
    LOW = "LOW"
    ILLIQUID = "ILLIQUID"


TIER_BASE_SCORES = {
    LiquidityTier.ULTRA_LIQUID: 0.95,
    LiquidityTier.HIGHLY_LIQUID: 0.85,
    LiquidityTier.LIQUID: 0.75,
    LiquidityTier.MODERATE: 0.60,
    LiquidityTier.LOW: 0.40,
    LiquidityTier.ILLIQUID: 0.15,
}


@dataclass
class LiquidityScoreResult:
    """Liquidity scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1
    tier: LiquidityTier = LiquidityTier.MODERATE
    volume_score: float = 0.0
    spread_score: float = 0.0
    depth_score: float = 0.0
    turnover_score: float = 0.0
    volatility_adj: float = 0.0
    regime_multiplier: float = 1.0
    max_allocation: float = 0.0
    adjusted_max: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"LiquidityScore[{self.strategy_id}] score={self.score:.3f} "
            f"tier={self.tier.value} max={self.max_allocation:,.0f}/"
            f"adj={self.adjusted_max:,.0f}"
        )


class LiquidityScorer:
    """Scores strategies based on liquidity quality for allocation sizing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._volume_weight = self._config.get("volume_weight", 0.30)
        self._spread_weight = self._config.get("spread_weight", 0.25)
        self._depth_weight = self._config.get("depth_weight", 0.20)
        self._volatility_weight = self._config.get("volatility_weight", 0.15)
        self._turnover_weight = self._config.get("turnover_weight", 0.10)

    def score(self, strategy_id: str,
              volume_score: float = 0.5,
              spread_score: float = 0.5,
              depth_score: float = 0.5,
              volatility_score: float = 0.5,
              turnover_score: float = 0.5,
              regime_multiplier: float = 1.0,
              max_allocation: float = 0.0,
              tier: LiquidityTier = LiquidityTier.MODERATE) -> LiquidityScoreResult:
        """Compute liquidity score for a strategy.

        Score = Σ(w_k * score_k) * regime_multiplier
        """
        base_score = (
            self._volume_weight * volume_score +
            self._spread_weight * spread_score +
            self._depth_weight * depth_score +
            self._volatility_weight * volatility_score +
            self._turnover_weight * turnover_score
        )

        # Blend with tier base score
        tier_base = TIER_BASE_SCORES.get(tier, 0.50)
        blended = 0.6 * base_score + 0.4 * tier_base

        # Apply regime multiplier
        final_score = blended * regime_multiplier

        # Adjust max allocation based on score
        adjusted_max = max_allocation
        if max_allocation > 0:
            if final_score < 0.42:
                adjusted_max = max_allocation * 0.467  # ~7M/15M

        return LiquidityScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, final_score)),
            tier=tier,
            volume_score=volume_score,
            spread_score=spread_score,
            depth_score=depth_score,
            turnover_score=turnover_score,
            volatility_adj=volatility_score,
            regime_multiplier=regime_multiplier,
            max_allocation=max_allocation,
            adjusted_max=adjusted_max,
        )

    def score_from_metrics(self, strategy_id: str,
                           daily_volume: float,
                           bid_ask_spread_bps: float,
                           order_book_depth: float,
                           volatility: float,
                           turnover_ratio: float,
                           regime_multiplier: float = 1.0,
                           max_allocation: float = 0.0) -> LiquidityScoreResult:
        """Compute liquidity score from raw market metrics."""
        # Volume: normalize to 0-1 (assume $100M/day is excellent)
        vol_score = min(1.0, daily_volume / 100_000_000.0)

        # Spread: 1bp = excellent, 100bp = terrible
        spread_score = max(0.0, 1.0 - bid_ask_spread_bps / 100.0)

        # Depth: normalize (assume $10M depth is excellent)
        depth_score = min(1.0, order_book_depth / 10_000_000.0)

        # Volatility: lower is better for liquidity
        vol_score = max(0.0, 1.0 - volatility / 0.50)

        # Turnover: higher is better
        turnover_score = min(1.0, turnover_ratio / 2.0)

        # Determine tier
        composite = (vol_score + spread_score + depth_score) / 3
        if composite > 0.85:
            tier = LiquidityTier.ULTRA_LIQUID
        elif composite > 0.70:
            tier = LiquidityTier.HIGHLY_LIQUID
        elif composite > 0.55:
            tier = LiquidityTier.LIQUID
        elif composite > 0.35:
            tier = LiquidityTier.MODERATE
        elif composite > 0.15:
            tier = LiquidityTier.LOW
        else:
            tier = LiquidityTier.ILLIQUID

        return self.score(
            strategy_id=strategy_id,
            volume_score=vol_score,
            spread_score=spread_score,
            depth_score=depth_score,
            volatility_score=vol_score,
            turnover_score=turnover_score,
            regime_multiplier=regime_multiplier,
            max_allocation=max_allocation,
            tier=tier,
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[LiquidityScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if all(k in params for k in ("daily_volume", "bid_ask_spread_bps")):
                result = self.score_from_metrics(strategy_id=sid, **params)
            else:
                result = self.score(strategy_id=sid, **params)
            results.append(result)
        return results
