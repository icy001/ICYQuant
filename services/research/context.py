"""
Experiment execution context.
"""

from dataclasses import dataclass


@dataclass
class ExperimentContext:
    dataset: str
    parameter_version: str
    strategy_id: str