"""
Experiment metadata.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentMetadata:
    strategy: str
    dataset: str
    description: str