"""
Experiment configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentConfiguration:
    config_version: str
    values: dict