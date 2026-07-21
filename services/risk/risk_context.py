"""
Risk evaluation context.
"""

from dataclasses import dataclass


@dataclass
class RiskContext:

    account_id: str

    portfolio_id: str

    order: dict

    market: dict

    positions: dict