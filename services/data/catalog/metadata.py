"""
Dataset metadata definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metadata:
    key: str
    value: str