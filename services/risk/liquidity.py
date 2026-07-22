"""
Liquidity risk model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidityProfile:

    symbol: str

    average_volume: float

    average_turnover: float