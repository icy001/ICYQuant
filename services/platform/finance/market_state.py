"""
Market state representation.
"""

from dataclasses import dataclass


@dataclass
class MarketState:

    timestamp: str

    equities: dict

    bonds: dict

    commodities: dict

    currencies: dict