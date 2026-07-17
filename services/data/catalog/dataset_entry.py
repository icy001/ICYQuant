"""
Dataset catalog entry.
"""

from dataclasses import dataclass
from .metadata import Metadata


@dataclass(frozen=True)
class DatasetEntry:
    name: str
    description: str
    metadata: list[Metadata]