"""
PostgreSQL audit persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.database.models import (
    AuditRecordModel,
)


class PostgreSQLAuditStore:
    def __init__(
        self,
        session,
    ):
        self.session = session

    def append(
        self,
        record,
    ):
        model = AuditRecordModel(
            id=str(
                record.audit_id
            ),
            action=
            record.action,
            reason=
            record.reason,
            created_at=datetime.now(
                timezone.utc
            )
        )
        self.session.add(
            model
        )
        self.session.commit()