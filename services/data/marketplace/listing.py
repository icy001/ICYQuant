"""
Dataset marketplace listing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetListing:
    dataset: str
    publisher: str
    description: str
    status: str = "PUBLISHED"