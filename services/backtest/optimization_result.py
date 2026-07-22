"""
Optimization result model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimizationResult:

    parameters: dict

    score: float