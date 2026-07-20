"""
Experiment result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    return_rate: float
    sharpe_ratio: float