"""
Portfolio position model.
"""

from dataclasses import dataclass


@dataclass
class PortfolioPosition:

    symbol: str

    quantity: float

    weight: float