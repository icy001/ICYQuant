"""
Research experiment model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    name: str
    owner: str
    status: str