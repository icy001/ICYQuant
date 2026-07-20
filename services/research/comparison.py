"""
Experiment comparison model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentComparison:
    left: str
    right: str
    metric: str
    winner: str