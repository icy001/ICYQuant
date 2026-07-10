"""
Audit store tests.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.audit import (
    SQLiteAuditStore,
    AuditRecord,
)


def test_sqlite_store_append_and_list_all():
    with tempfile.NamedTemporaryFile(
        suffix=".db", delete=False
    ) as f:
        db_path = f.name

    try:
        store = SQLiteAuditStore(db_path)

        reference_id = uuid4()
        before = {"cash": 10000.0}
        after = {"cash": 9950.0}
        created_at = datetime.now(timezone.utc)

        record = AuditRecord(
            audit_id=uuid4(),
            action="COMMISSION_CHARGED",
            source="broker",
            reference_id=reference_id,
            before=before,
            after=after,
            reason="Trade commission",
            created_at=created_at,
        )

        store.append(record)

        records = store.list_all()
        assert len(records) == 1
        retrieved = records[0]
        assert retrieved.audit_id == record.audit_id
        assert retrieved.action == "COMMISSION_CHARGED"
        assert retrieved.source == "broker"
        assert retrieved.reference_id == reference_id
        assert retrieved.before == before
        assert retrieved.after == after
        assert retrieved.reason == "Trade commission"
    finally:
        store.connection.close()
        os.unlink(db_path)


def test_sqlite_store_multiple_records():
    with tempfile.NamedTemporaryFile(
        suffix=".db", delete=False
    ) as f:
        db_path = f.name

    try:
        store = SQLiteAuditStore(db_path)

        record1 = AuditRecord(
            audit_id=uuid4(),
            action="ORDER_CREATED",
            source="oms",
            reference_id=None,
            before={},
            after={"order_id": "1"},
            reason="New order",
            created_at=datetime.now(timezone.utc),
        )

        record2 = AuditRecord(
            audit_id=uuid4(),
            action="ORDER_FILLED",
            source="execution",
            reference_id=None,
            before={"status": "pending"},
            after={"status": "filled"},
            reason="Order executed",
            created_at=datetime.now(timezone.utc),
        )

        store.append(record1)
        store.append(record2)

        records = store.list_all()
        assert len(records) == 2
        assert records[0].action == "ORDER_CREATED"
        assert records[1].action == "ORDER_FILLED"
    finally:
        store.connection.close()
        os.unlink(db_path)


def test_sqlite_store_empty_list():
    with tempfile.NamedTemporaryFile(
        suffix=".db", delete=False
    ) as f:
        db_path = f.name

    try:
        store = SQLiteAuditStore(db_path)
        records = store.list_all()
        assert len(records) == 0
    finally:
        store.connection.close()
        os.unlink(db_path)


def test_sqlite_store_null_reference_id():
    with tempfile.NamedTemporaryFile(
        suffix=".db", delete=False
    ) as f:
        db_path = f.name

    try:
        store = SQLiteAuditStore(db_path)

        record = AuditRecord(
            audit_id=uuid4(),
            action="SYSTEM_CHECK",
            source="health",
            reference_id=None,
            before={"status": "unknown"},
            after={"status": "healthy"},
            reason="Health check",
            created_at=datetime.now(timezone.utc),
        )

        store.append(record)
        records = store.list_all()
        assert len(records) == 1
        assert records[0].reference_id is None
    finally:
        store.connection.close()
        os.unlink(db_path)