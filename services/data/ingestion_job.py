"""
Market data ingestion job.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IngestionJob:

    job_id: str

    source: str

    dataset: str

    created_at: datetime

    status: str