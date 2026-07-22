"""
Concentration limit.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConcentrationLimit:

    asset: str

    max_weight: float