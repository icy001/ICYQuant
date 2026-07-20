"""
Optimization result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimizationResult:
    best_parameters: object