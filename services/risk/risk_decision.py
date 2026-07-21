"""
Unified risk decision.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:

    approved: bool

    score: float

    reason: str