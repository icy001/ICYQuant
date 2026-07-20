"""
Experiment manifest.
"""

from dataclasses import dataclass

from .environment import EnvironmentSnapshot
from .configuration import ExperimentConfiguration


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    dataset_version: str
    strategy_version: str
    environment: EnvironmentSnapshot
    configuration: ExperimentConfiguration