"""
Concentration risk model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Concentration:

    portfolio_id: str

    asset: str

    weight: float