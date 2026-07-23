"""
Portfolio context model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioContext:

    portfolio_id: str

    holdings: list

    cash: float

    metadata: dict