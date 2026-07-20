"""
Experiment snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentSnapshot:
    experiment_id: str
    metrics: dict[str, float]