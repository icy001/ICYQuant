"""
Audit service.

Creates audit records
for reconciliation actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .model import AuditRecord


class AuditService:
    def __init__(
        self,
        store,
    ):
        self.store = store

    def record(
        self,
        action: str,
        source: str,
        before: dict,
        after: dict,
        reason: str,
        reference_id=None,
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=uuid4(),
            action=action,
            source=source,
            reference_id=reference_id,
            before=before,
            after=after,
            reason=reason,
            created_at=datetime.now(
                timezone.utc
            )
        )
        self.store.append(
            record
        )
        return record