"""
Portfolio recovery models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RecoveryRecord:

    recovery_id: str

    snapshot_id: str

    created_at: datetime

    status: str