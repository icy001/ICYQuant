"""
Parameter search space.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterSpace:

    parameters: dict