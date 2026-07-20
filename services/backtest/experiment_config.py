"""
Experiment configuration snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentConfig:
    parameters: dict
    dataset: str
    initial_cash: float