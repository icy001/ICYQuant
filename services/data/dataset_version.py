"""
Dataset version model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetVersion:

    dataset_id: str

    version: str

    created_at: datetime

    description: str