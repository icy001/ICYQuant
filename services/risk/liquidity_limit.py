"""
Liquidity limit.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidityLimit:

    max_volume_ratio: float

    max_market_impact: float