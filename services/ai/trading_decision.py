"""
AI trading decision model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingDecision:

    symbol: str

    action: str

    confidence: float

    reasoning: str