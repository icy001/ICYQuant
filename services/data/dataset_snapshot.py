"""
Dataset snapshot.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetSnapshot:

    snapshot_id: str

    dataset_id: str

    version: str

    created_at: datetime

    location: str