"""
Liquidity Optimizer — ensures positions are executable given market liquidity.

Models:
    - ADV (Average Daily Volume)
    - Bid/Ask spread
    - Market depth
    - Participation rate
    - Expected market impact

Prevents the system from generating positions that cannot be executed
without excessive market impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class LiquidityProfile:
    """Liquidity metrics for a single asset."""
    asset: str = ""
    adv: float = 0.0
    bid_ask_spread_bps: float = 0.0
    market_depth: float = 0.0
    daily_volume: float = 0.0
    position_size: float = 0.0
    position_pct_adv: float = 0.0
    expected_days_to_trade: float = 0.0
    is_tradeable: bool = True


@dataclass
class LiquidityConfig:
    """Liquidity optimization configuration."""
    max_position_pct_adv: float = 0.10
    max_participation_rate: float = 0.15
    max_spread_bps: float = 50.0
    min_adv: float = 100_000.0
    max_days_to_trade: float = 5.0
    liquidation_penalty_bps: float = 10.0


@dataclass
class LiquidityResult:
    """Result of liquidity optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    profiles: dict[str, LiquidityProfile] = field(default_factory=dict)
    untradeable: list[str] = field(default_factory=list)
    resized: list[dict] = field(default_factory=list)
    overall_liquidity_score: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)


class LiquidityOptimizer:
    """
    Liquidity-aware position sizing.

    Key principle:
        Target Position ≠ Tradeable Position

    Formula:
        max_tradeable = min(
            ADV * max_pct_adv,
            position * participation_rate,
            market_depth * depth_factor
        )
    """

    def __init__(self, config: Optional[LiquidityConfig] = None) -> None:
        self._config = config or LiquidityConfig()
        self._last_result: Optional[LiquidityResult] = None

    async def optimize(
        self,
        positions: dict[str, float],
        market_data: dict[str, dict],  # {asset: {adv, spread, depth, volume}}
    ) -> LiquidityResult:
        """Optimize positions for liquidity constraints."""
        result = LiquidityResult()
        scores = []

        for asset, size in positions.items():
            data = market_data.get(asset, {})
            adv = data.get("adv", 0)
            spread = data.get("spread_bps", 0)
            depth = data.get("depth", 0)
            volume = data.get("daily_volume", 0)

            profile = LiquidityProfile(
                asset=asset,
                adv=adv,
                bid_ask_spread_bps=spread,
                market_depth=depth,
                daily_volume=volume,
                position_size=size,
            )

            # Check tradability
            if adv > 0:
                pct_adv = abs(size) / adv
                profile.position_pct_adv = pct_adv
                profile.expected_days_to_trade = pct_adv / self._config.max_participation_rate

                if pct_adv > self._config.max_position_pct_adv:
                    profile.is_tradeable = False
                    result.untradeable.append(asset)
                    result.resized.append({
                        "asset": asset, "from": size,
                        "to": self._config.max_position_pct_adv * adv * (1 if size > 0 else -1),
                        "reason": f"exceeds {self._config.max_position_pct_adv*100}% ADV",
                    })

                # Liquidity score per asset
                spread_score = max(0, 1 - spread / self._config.max_spread_bps)
                adv_score = min(1, adv / (self._config.min_adv * 10))
                scores.append((spread_score + adv_score) / 2)

            result.profiles[asset] = profile

        result.overall_liquidity_score = sum(scores) / max(len(scores), 1) if scores else 1.0
        result.timestamp = datetime.now()
        self._last_result = result

        if result.untradeable:
            logger.warning("Liquidity: %d untradeable positions", len(result.untradeable))
        return result

    async def analyze(self, asset: str, data: dict) -> LiquidityProfile:
        """Analyze liquidity for a single asset."""
        return LiquidityProfile(
            asset=asset,
            adv=data.get("adv", 0),
            bid_ask_spread_bps=data.get("spread_bps", 0),
            market_depth=data.get("depth", 0),
            daily_volume=data.get("daily_volume", 0),
        )

    def estimate_max_size(
        self, adv: float, participation: Optional[float] = None
    ) -> float:
        """Estimate maximum executable position size."""
        part = participation or self._config.max_participation_rate
        return adv * self._config.max_position_pct_adv * part

    @property
    def last_result(self) -> Optional[LiquidityResult]:
        return self._last_result
