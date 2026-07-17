"""
Quality rule definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityRule:
    name: str
    description: str