"""
Risk decision model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:

    portfolio_id: str

    risk_level: str

    confidence: float

    recommendation: str