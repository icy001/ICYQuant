"""
Experiment parameter model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentParameter:
    name: str
    value: str
    parameter_type: str