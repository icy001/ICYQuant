"""
Tests for LedgerEvent domain — LEDGER_ENTRY_CREATED, LEDGER_BATCH_POSTED.

Coverage:
- Event creation with basic fields
- Lineage propagation (correlation_id, causation_id, lineage_id)
- Serialization to_dict / from_dict round-trip
- LedgerBatchPostedEvent with batch_entry_ids
"""

from datetime import datetime, timezone

from services.ledger.domain.ledger_event import (
    LedgerBatchPostedEvent,
    LedgerEntryCreatedEvent,
    LedgerEvent,
    LedgerEventType,
)


class TestLedgerEvent:
    """Tests for base LedgerEvent."""

    def test_create_entry_created_event(self) -> None:
        event = LedgerEvent(
            event_type=LedgerEventType.LEDGER_ENTRY_CREATED,
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert event.event_type == "LEDGER_ENTRY_CREATED"
        assert event.entry_id == "LEDGER-001"
        assert event.account_id == "ACC-001"
        assert event.execution_id == "EXEC-001"

    def test_event_has_timestamp(self) -> None:
        event = LedgerEvent(
            event_type=LedgerEventType.LEDGER_ENTRY_CREATED,
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert isinstance(event.timestamp, datetime)

    def test_event_with_lineage(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-STRATEGY-001",
            causation_id="EVT-001",
            lineage_id="LINE-STRATEGY-001",
        )
        assert event.correlation_id == "CORR-STRATEGY-001"
        assert event.causation_id == "EVT-001"
        assert event.lineage_id == "LINE-STRATEGY-001"

    def test_event_with_batch_id(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            batch_id="BATCH-001",
        )
        assert event.batch_id == "BATCH-001"

    def test_event_with_version(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            version=42,
        )
        assert event.version == 42


class TestLedgerEventSerialization:
    """Tests for LedgerEvent serialization round-trip."""

    def test_to_dict_contains_all_fields(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LINE-001",
            batch_id="BATCH-001",
        )
        d = event.to_dict()
        assert d["event_type"] == "LEDGER_ENTRY_CREATED"
        assert d["entry_id"] == "LEDGER-001"
        assert d["correlation_id"] == "CORR-001"
        assert d["batch_id"] == "BATCH-001"

    def test_from_dict_roundtrip(self) -> None:
        original = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
        )
        d = original.to_dict()
        restored = LedgerEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.entry_id == original.entry_id
        assert restored.account_id == original.account_id
        assert restored.amount == original.amount
        assert restored.correlation_id == original.correlation_id

    def test_from_dict_batch_posted_event(self) -> None:
        batch_event = LedgerBatchPostedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=100000.0,
            credit=100000.0,
            amount=0.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            batch_entry_ids=["LEDGER-001", "LEDGER-002"],
            total_debit=100000.0,
            total_credit=100000.0,
        )
        d = batch_event.to_dict()
        restored = LedgerEvent.from_dict(d)
        assert restored.event_type == "LEDGER_BATCH_POSTED"
        assert isinstance(restored, LedgerBatchPostedEvent)
        assert restored.total_debit == 100000.0


class TestLedgerEntryCreatedEvent:
    """Tests for LedgerEntryCreatedEvent."""

    def test_convenience_init(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="FEE",
            debit=10.0,
            credit=0.0,
            amount=-10.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert event.event_type == "LEDGER_ENTRY_CREATED"
        assert event.entry_type == "FEE"
        assert event.debit == 10.0

    def test_trade_entry_created_default_type(self) -> None:
        event = LedgerEntryCreatedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert event.event_type == LedgerEventType.LEDGER_ENTRY_CREATED


class TestLedgerBatchPostedEvent:
    """Tests for LedgerBatchPostedEvent."""

    def test_batch_posted_with_entry_ids(self) -> None:
        event = LedgerBatchPostedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=100000.0,
            credit=100000.0,
            amount=0.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            batch_entry_ids=["LEDGER-001", "LEDGER-002", "LEDGER-003"],
            total_debit=100000.0,
            total_credit=100000.0,
        )
        assert len(event.batch_entry_ids) == 3
        assert event.total_debit == 100000.0
        assert event.total_credit == 100000.0

    def test_batch_posted_default_entry_ids(self) -> None:
        event = LedgerBatchPostedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=0.0,
            credit=0.0,
            amount=0.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert event.batch_entry_ids == []
        assert event.total_debit == 0.0
        assert event.total_credit == 0.0

    def test_batch_to_dict_includes_entry_ids(self) -> None:
        event = LedgerBatchPostedEvent(
            entry_id="LEDGER-001",
            account_id="ACC-001",
            currency="USD",
            entry_type="TRADE",
            debit=100000.0,
            credit=100000.0,
            amount=0.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            batch_entry_ids=["LEDGER-001", "LEDGER-002"],
            total_debit=100000.0,
            total_credit=100000.0,
        )
        d = event.to_dict()
        assert d["batch_entry_ids"] == ["LEDGER-001", "LEDGER-002"]
        assert d["total_debit"] == 100000.0
        assert d["total_credit"] == 100000.0
