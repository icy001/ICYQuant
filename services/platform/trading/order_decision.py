"""
Order decision model.
"""

from dataclasses import dataclass


@dataclass
class OrderDecision:

    symbol: str

    side: str

    quantity: float

    confidence: float