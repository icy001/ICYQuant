"""Tests for the repair record repository."""

from datetime import datetime, timezone
from decimal import Decimal

from services.reconciliation.models.repair import (
    RepairActionType,
    RepairStatus,
)
from services.reconciliation.models.repair_record import RepairRecord
from services.reconciliation.repair_repository import InMemoryRepairRepository


def make_record(
    repair_id: str = "REPAIR-20260814-000001",
    reconciliation_id: str = "REC-20260814-000001",
    status: RepairStatus = RepairStatus.EXECUTED,
) -> RepairRecord:
    return RepairRecord(
        repair_id=repair_id,
        reconciliation_id=reconciliation_id,
        action=RepairActionType.REBUILD_POSITION,
        status=status,
        reason="Quantity mismatch",
        before_quantity=Decimal("80"),
        before_average_price=Decimal("180"),
        before_realized_pnl=Decimal("900"),
        after_quantity=Decimal("100"),
        after_average_price=Decimal("175"),
        after_realized_pnl=Decimal("1200"),
        attempt=1,
        created_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 14, 12, 0, 1, tzinfo=timezone.utc),
    )


def test_create_and_get_repair_record():
    repo = InMemoryRepairRepository()
    record = make_record()

    repo.create(record)

    assert repo.get("REPAIR-20260814-000001") == record


def test_update_repair_record():
    repo = InMemoryRepairRepository()
    repo.create(make_record(status=RepairStatus.EXECUTING))

    updated = make_record(status=RepairStatus.EXECUTED)
    repo.update(updated)

    assert repo.get("REPAIR-20260814-000001").status == RepairStatus.EXECUTED


def test_get_missing_returns_none():
    repo = InMemoryRepairRepository()

    assert repo.get("REPAIR-MISSING") is None


def test_list_by_reconciliation():
    repo = InMemoryRepairRepository()
    repo.create(make_record(repair_id="REPAIR-20260814-000001"))
    repo.create(make_record(repair_id="REPAIR-20260814-000002"))
    repo.create(
        make_record(
            repair_id="REPAIR-20260814-000003",
            reconciliation_id="REC-20260814-000002",
        )
    )

    records = repo.list_by_reconciliation("REC-20260814-000001")

    assert [record.repair_id for record in records] == [
        "REPAIR-20260814-000001",
        "REPAIR-20260814-000002",
    ]
