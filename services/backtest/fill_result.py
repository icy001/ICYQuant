"""
Virtual fill result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FillResult:

    filled_quantity: float

    average_price: float

    commission: float

    slippage: float