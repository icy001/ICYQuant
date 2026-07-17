"""
Dataset snapshot.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetSnapshot:
    dataset: str
    version: str
    created_at: datetime