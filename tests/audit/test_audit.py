"""
Audit service tests.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from services.audit import (
    AuditService,
    AuditRecord,
    SQLiteAuditStore,
)


class MockAuditStore:
    def __init__(self):
        self.records = []

    def append(self, record: AuditRecord):
        self.records.append(record)

    def list_all(self):
        return self.records


def test_audit_record_creation():
    audit_id = uuid4()
    reference_id = uuid4()
    before = {"balance": 1000}
    after = {"balance": 900}

    record = AuditRecord(
        audit_id=audit_id,
        action="BALANCE_ADJUSTED",
        source="reconciliation",
        reference_id=reference_id,
        before=before,
        after=after,
        reason="Daily settlement",
        created_at=None,
    )

    assert record.audit_id == audit_id
    assert record.action == "BALANCE_ADJUSTED"
    assert record.source == "reconciliation"
    assert record.reference_id == reference_id
    assert record.before == before
    assert record.after == after
    assert record.reason == "Daily settlement"


def test_audit_service_record():
    store = MockAuditStore()
    service = AuditService(store)

    before = {"quantity": 100}
    after = {"quantity": 90}
    reference_id = uuid4()

    record = service.record(
        action="POSITION_ADJUSTED",
        source="repair_service",
        before=before,
        after=after,
        reason="Reconciliation fix",
        reference_id=reference_id,
    )

    assert isinstance(record, AuditRecord)
    assert record.action == "POSITION_ADJUSTED"
    assert record.source == "repair_service"
    assert record.reference_id == reference_id
    assert record.before == before
    assert record.after == after
    assert record.reason == "Reconciliation fix"
    assert record.created_at is not None


def test_audit_service_record_no_reference_id():
    store = MockAuditStore()
    service = AuditService(store)

    record = service.record(
        action="SYSTEM_STARTED",
        source="app",
        before={},
        after={"status": "running"},
        reason="Application startup",
    )

    assert record.reference_id is None
    assert len(store.records) == 1


def test_audit_record_immutable():
    record = AuditRecord(
        audit_id=uuid4(),
        action="TEST",
        source="test",
        reference_id=None,
        before={},
        after={},
        reason="test",
        created_at=None,
    )

    with pytest.raises(AttributeError):
        record.action = "MODIFIED"


def test_audit_record(
    tmp_path,
):
    db = (
        tmp_path /
        "audit.db"
    )

    store = SQLiteAuditStore(
        str(db)
    )

    service = AuditService(
        store
    )

    record = service.record(
        action=
        "POSITION_REPAIR",
        source=
        "RECONCILIATION",
        before={
            "NVDA":
            80
        },
        after={
            "NVDA":
            100
        },
        reason=
        "BROKER_MISMATCH"
    )

    records = store.list_all()

    assert len(records) == 1

    assert (
        records[0].action
        ==
        "POSITION_REPAIR"
    )