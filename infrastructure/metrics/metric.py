"""
Metric base model.
"""

from dataclasses import dataclass


@dataclass
class Metric:

    name: str

    value: float

    labels: dict