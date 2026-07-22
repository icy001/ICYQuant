"""
Margin requirement model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarginRequirement:

    symbol: str

    initial_margin_ratio: float

    maintenance_margin_ratio: float