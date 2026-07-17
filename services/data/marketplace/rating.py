"""
Dataset rating.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetRating:
    dataset: str
    score: float
    reviewer: str