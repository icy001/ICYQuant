"""
Audit domain models.

Every important system action
must produce an audit record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(
    frozen=True,
)
class AuditRecord:
    """
    Immutable audit entry.
    """

    __slots__ = (
        "audit_id",
        "action",
        "source",
        "reference_id",
        "before",
        "after",
        "reason",
        "created_at",
    )

    audit_id: UUID
    action: str
    source: str
    reference_id: UUID | None
    before: dict
    after: dict
    reason: str
    created_at: datetime