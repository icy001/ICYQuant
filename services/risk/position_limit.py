"""
Position limit model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionLimit:

    symbol: str

    max_quantity: float