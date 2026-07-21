"""
Portfolio audit models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditRecord:

    audit_id: str

    entity: str

    action: str

    operator: str

    created_at: datetime

    details: dict