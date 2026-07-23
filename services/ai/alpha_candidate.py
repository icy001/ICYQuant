"""
Alpha candidate model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaCandidate:

    name: str

    factor_expression: str

    category: str

    metadata: dict