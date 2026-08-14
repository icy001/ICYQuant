"""Repair record persistence."""

from __future__ import annotations

from typing import Protocol

from .models.repair_record import RepairRecord


class RepairRepository(Protocol):
    def create(self, record: RepairRecord) -> None: ...

    def update(self, record: RepairRecord) -> None: ...

    def get(self, repair_id: str) -> RepairRecord | None: ...

    def list_by_reconciliation(
        self,
        reconciliation_id: str,
    ) -> list[RepairRecord]: ...


class InMemoryRepairRepository:
    """In-memory implementation for tests and single-process deployments."""

    def __init__(self) -> None:
        self._records: dict[str, RepairRecord] = {}

    def create(self, record: RepairRecord) -> None:
        self._records[record.repair_id] = record

    def update(self, record: RepairRecord) -> None:
        self._records[record.repair_id] = record

    def get(self, repair_id: str) -> RepairRecord | None:
        return self._records.get(repair_id)

    def list_by_reconciliation(
        self,
        reconciliation_id: str,
    ) -> list[RepairRecord]:
        return [
            record
            for record in self._records.values()
            if record.reconciliation_id == reconciliation_id
        ]
