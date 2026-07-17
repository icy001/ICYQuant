"""
Dataset version.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetVersion:
    dataset_name: str
    version: str