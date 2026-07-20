"""
Strategy parameter definition.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ParameterRange:
    name: str
    values: List