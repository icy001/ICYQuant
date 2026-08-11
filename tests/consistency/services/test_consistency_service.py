"""Tests for ConsistencyService."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.consistency.domain.consistency_check import ExecutionFact, LedgerView, PositionView
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.events.consistency_failed import ConsistencyFailed
from services.consistency.events.consistency_restored import ConsistencyRestored
from services.consistency.services.consistency_service import ConsistencyService


NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


def _fact(
    execution_id: str = "EXEC-001",
    account_id: str = "ACC-001",
    instrument_id: str = "NVDA",
    side: str = "BUY",
    fill_quantity: float = 1000,
    fill_price: float = 180.0,
) -> ExecutionFact:
    return ExecutionFact(
        execution_id=execution_id,
        order_id=f"ORD-{execution_id[-3:]}",
        account_id=account_id,
        instrument_id=instrument_id,
        side=side,
        fill_quantity=fill_quantity,
        fill_price=fill_price,
        occurred_at=NOW,
    )


def _pos(
    account_id: str = "ACC-001",
    instrument_id: str = "NVDA",
    quantity: float = 1000,
) -> PositionView:
    return PositionView(
        position_id=f"POS-{account_id}-{instrument_id}",
        account_id=account_id,
        instrument_id=instrument_id,
        side="LONG",
        quantity=quantity,
        version=1,
        last_updated_at=NOW,
    )


def _ledger(
    account_id: str = "ACC-001",
    trade_amount: float = 180000.0,
) -> LedgerView:
    return LedgerView(
        account_id=account_id,
        currency="USD",
        trade_amount=trade_amount,
        fee_amount=0.0,
        commission_amount=0.0,
        balance=-trade_amount,
        version=1,
        last_updated_at=NOW,
    )


# ------------------------------------------------------------------
#  Service factory
# ------------------------------------------------------------------

@pytest.fixture
def svc() -> ConsistencyService:
    return ConsistencyService(grace_period_ms=5000)


# ------------------------------------------------------------------
#  Recording snapshots
# ------------------------------------------------------------------

class TestRecording:
    def test_record_execution_adds_fact(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact("EXEC-001"))
        svc.record_execution(_fact("EXEC-002"))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert len(check.execution_facts) == 2

    def test_record_position_overwrites(self, svc: ConsistencyService) -> None:
        svc.record_position(_pos(quantity=500))
        svc.record_position(_pos(quantity=1000))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.position_view is not None
        assert check.position_view.quantity == 1000

    def test_record_ledger_overwrites(self, svc: ConsistencyService) -> None:
        svc.record_ledger(_ledger(trade_amount=50000.0))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.ledger_view is not None
        assert check.ledger_view.trade_amount == 180000.0


# ------------------------------------------------------------------
#  Scoped checks
# ------------------------------------------------------------------

class TestCheckInstrument:
    def test_consistent_instrument(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact("EXEC-001", fill_quantity=1000, fill_price=180.0))
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.is_consistent
        assert check.overall_status == ConsistencyDomainStatus.CONSISTENT

    def test_position_mismatch(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.is_inconsistent

    def test_ledger_mismatch(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact())
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=0.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.is_inconsistent

    def test_no_execution_facts(self, svc: ConsistencyService) -> None:
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.overall_status == ConsistencyDomainStatus.DEGRADED

    def test_check_multiple_instruments(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact("EXEC-001", instrument_id="NVDA"))
        svc.record_execution(_fact("EXEC-002", instrument_id="AAPL"))
        svc.record_position(_pos(instrument_id="NVDA", quantity=1000))
        svc.record_position(_pos(instrument_id="AAPL", quantity=200))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        nvda_check = svc.check_instrument("ACC-001", "NVDA")
        aapl_check = svc.check_instrument("ACC-001", "AAPL")
        assert nvda_check.is_consistent
        assert not aapl_check.is_consistent  # No matching ledger for AAPL


class TestCheckExecution:
    def test_single_execution(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact("EXEC-001", fill_quantity=300, fill_price=180.0))
        svc.record_execution(_fact("EXEC-002", fill_quantity=700, fill_price=181.0))
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=300 * 180 + 700 * 181))
        check = svc.check_execution("EXEC-001", "ACC-001", "NVDA")
        assert len(check.execution_facts) == 1
        assert check.execution_facts[0].execution_id == "EXEC-001"

    def test_execution_not_found(self, svc: ConsistencyService) -> None:
        check = svc.check_execution("EXEC-999", "ACC-001", "NVDA")
        assert check.execution_facts == []


class TestCheckOrder:
    def test_order_with_multiple_fills(self, svc: ConsistencyService) -> None:
        # Both fills from the same order ORD-001
        fact1 = ExecutionFact(
            execution_id="EXEC-001",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=300,
            fill_price=180.0,
            occurred_at=NOW,
        )
        fact2 = ExecutionFact(
            execution_id="EXEC-002",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=700,
            fill_price=181.0,
            occurred_at=NOW,
        )
        svc.record_execution(fact1)
        svc.record_execution(fact2)
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=300 * 180 + 700 * 181))
        check = svc.check_order("ORD-001", "ACC-001", "NVDA")
        assert len(check.execution_facts) == 2
        assert check.is_consistent

    def test_order_not_found(self, svc: ConsistencyService) -> None:
        check = svc.check_order("ORD-999", "ACC-001", "NVDA")
        assert len(check.execution_facts) == 0


class TestCheckAccount:
    def test_multiple_instruments(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact("EXEC-001", instrument_id="NVDA"))
        svc.record_execution(_fact("EXEC-002", instrument_id="AAPL"))
        svc.record_position(_pos(instrument_id="NVDA", quantity=1000))
        svc.record_position(_pos(instrument_id="AAPL", quantity=200))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        checks = svc.check_account("ACC-001")
        assert len(checks) == 2

    def test_empty_account(self, svc: ConsistencyService) -> None:
        checks = svc.check_account("ACC-001")
        assert len(checks) == 0


# ------------------------------------------------------------------
#  Event emission
# ------------------------------------------------------------------

class TestEventEmission:
    def test_failure_event_emitted(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))  # mismatch
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")
        events = svc.get_events()
        failures = [e for e in events if isinstance(e, ConsistencyFailed)]
        assert len(failures) >= 1

    def test_no_event_when_consistent(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact())
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")
        events = svc.get_events()
        failures = [e for e in events if isinstance(e, ConsistencyFailed)]
        assert len(failures) == 0

    def test_failure_event_contains_details(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")
        events = svc.get_events()
        failures = [e for e in events if isinstance(e, ConsistencyFailed)]
        assert len(failures) >= 1
        event = failures[0]
        assert event.check_id != ""
        assert event.account_id == "ACC-001"
        assert event.domain != ""

    def test_failure_event_roundtrip(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")
        events = svc.get_events()
        failures = [e for e in events if isinstance(e, ConsistencyFailed)]
        assert len(failures) >= 1
        restored = ConsistencyFailed.from_dict(failures[0].to_dict())
        assert restored.check_id == failures[0].check_id
        assert restored.delta == failures[0].delta

    def test_restored_event_on_recovery(self, svc: ConsistencyService) -> None:
        # First: inconsistent
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")

        # Then: repaired
        svc.record_position(_pos(quantity=1000))
        svc.check_instrument("ACC-001", "NVDA")

        events = svc.get_events()
        restored_events = [e for e in events if isinstance(e, ConsistencyRestored)]
        assert len(restored_events) >= 1

    def test_custom_on_event_callback(self) -> None:
        captured: list = []

        def handler(event: object) -> None:
            captured.append(event)

        svc = ConsistencyService(grace_period_ms=5000, on_event=handler)
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        svc.check_instrument("ACC-001", "NVDA")
        assert len(captured) >= 1
        assert isinstance(captured[0], ConsistencyFailed)


# ------------------------------------------------------------------
#  Counters
# ------------------------------------------------------------------

class TestCounters:
    def test_check_count(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact())
        svc.record_position(_pos())
        svc.record_ledger(_ledger())
        assert svc.check_count == 0
        svc.check_instrument("ACC-001", "NVDA")
        assert svc.check_count == 1
        svc.check_instrument("ACC-001", "NVDA")
        assert svc.check_count == 2

    def test_event_count(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        assert svc.event_count == 0
        svc.check_instrument("ACC-001", "NVDA")
        assert svc.event_count == 1

    def test_get_check_by_id(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact())
        svc.record_position(_pos())
        svc.record_ledger(_ledger())
        check = svc.check_instrument("ACC-001", "NVDA")
        retrieved = svc.get_check(check.check_id)
        assert retrieved is not None
        assert retrieved.check_id == check.check_id


# ------------------------------------------------------------------
#  Trigger generation via RunConsistencyCheck
# ------------------------------------------------------------------

class TestTriggerGeneration:
    def test_triggers_generated_for_mismatch(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.has_triggers

    def test_triggers_have_priority(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact(fill_quantity=1000))
        svc.record_position(_pos(quantity=700))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert check.has_triggers
        # Verify triggers have valid priority
        for trigger in check.triggers:
            assert trigger.priority.value >= 0
            assert trigger.priority.value <= 3

    def test_no_triggers_when_consistent(self, svc: ConsistencyService) -> None:
        svc.record_execution(_fact())
        svc.record_position(_pos(quantity=1000))
        svc.record_ledger(_ledger(trade_amount=180000.0))
        check = svc.check_instrument("ACC-001", "NVDA")
        assert not check.has_triggers
