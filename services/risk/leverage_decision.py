"""
Leverage decision.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LeverageDecision:

    approved: bool

    leverage: float