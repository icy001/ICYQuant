"""
Parameter search space.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchSpace:
    parameters: dict[str, list]