"""
Parameter snapshot.
"""

from dataclasses import dataclass

from .parameter_group import ParameterGroup


@dataclass(frozen=True)
class ParameterSnapshot:
    experiment_id: str
    version: str
    group: ParameterGroup