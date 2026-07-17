"""
Audit trail.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditRecord:
    action: str
    timestamp: datetime