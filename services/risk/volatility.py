"""
Volatility risk model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VolatilityProfile:

    symbol: str

    value: float

    window: int