"""
Market intelligence context.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketContext:

    timestamp: str

    symbols: list

    macro_data: dict

    market_data: dict

    metadata: dict