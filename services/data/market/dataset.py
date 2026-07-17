"""
Dataset definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dataset:
    name: str
    version: str
    description: str