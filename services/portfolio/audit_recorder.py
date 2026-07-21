"""
Audit recorder.
"""

from datetime import datetime

from .audit import AuditRecord


class AuditRecorder:

    def record(
        self,
        audit_id,
        entity,
        action,
        operator,
        details,
    ):

        return AuditRecord(
            audit_id=audit_id,
            entity=entity,
            action=action,
            operator=operator,
            created_at=datetime.utcnow(),
            details=details,
        )