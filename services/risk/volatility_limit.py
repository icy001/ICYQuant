"""
Volatility limit.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VolatilityLimit:

    symbol: str

    max_volatility: float