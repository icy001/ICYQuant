"""
Optimization trial.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimizationTrial:
    trial_id: str
    parameters: dict[str, object]