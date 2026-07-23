"""
Investment OS context.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InvestmentOSContext:

    user_id: str

    objective: str

    portfolio_id: str

    metadata: dict