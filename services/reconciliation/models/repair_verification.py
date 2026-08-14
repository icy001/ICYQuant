from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RepairVerification:
    verified: bool
    reconciliation_status: str
    verified_at: datetime
    reason: str
