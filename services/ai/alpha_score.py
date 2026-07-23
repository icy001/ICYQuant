"""
Alpha ranking model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaScore:

    alpha_name: str

    sharpe: float

    return_score: float

    stability: float