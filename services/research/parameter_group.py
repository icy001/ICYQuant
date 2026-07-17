"""
Parameter group.
"""

from dataclasses import dataclass

from .parameter import ExperimentParameter


@dataclass
class ParameterGroup:
    group_name: str
    parameters: list[ExperimentParameter]