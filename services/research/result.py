"""
Experiment result.
"""

from dataclasses import dataclass


@dataclass
class ExperimentResult:
    experiment_id: str
    status: str