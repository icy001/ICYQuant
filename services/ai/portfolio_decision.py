"""
Portfolio decision model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioDecision:

    portfolio_id: str

    recommendation: str

    confidence: float

    reasoning: str