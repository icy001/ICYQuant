"""
Risk context model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskContext:

    portfolio_id: str

    positions: list

    market_state: dict

    metadata: dict