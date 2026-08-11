"""Tests for domain models: ExecutionFact, PositionView, LedgerView, ReconciliationTrigger, ConsistencyCheck."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.consistency.domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    LedgerView,
    PositionView,
    ReconciliationTrigger,
)
from services.consistency.domain.consistency_status import (
    ConsistencyDomainStatus,
    ReconciliationTriggerPriority,
)


NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------
#  ExecutionFact
# ------------------------------------------------------------------

class TestExecutionFact:
    def test_buy_fact(self) -> None:
        fact = ExecutionFact(
            execution_id="EXEC-001",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.0,
        )
        assert fact.execution_id == "EXEC-001"
        assert fact.side == "BUY"
        assert fact.trade_value == 180000.0

    def test_sell_fact(self) -> None:
        fact = ExecutionFact(
            execution_id="EXEC-002",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="AAPL",
            side="SELL",
            fill_quantity=500,
            fill_price=195.0,
        )
        assert fact.trade_value == 97500.0

    def test_with_fee_commission(self) -> None:
        fact = ExecutionFact(
            execution_id="EXEC-003",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.0,
            fee=10.0,
            commission=5.0,
        )
        assert fact.fee == 10.0
        assert fact.commission == 5.0
        assert fact.trade_value == 180000.0

    def test_roundtrip_via_dict(self) -> None:
        fact = ExecutionFact(
            execution_id="EXEC-001",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=1000,
            fill_price=180.0,
            fee=10.0,
            commission=5.0,
            currency="HKD",
            occurred_at=NOW,
        )
        restored = ExecutionFact.from_dict(fact.to_dict())
        assert restored.execution_id == fact.execution_id
        assert restored.trade_value == fact.trade_value
        assert restored.fee == fact.fee
        assert restored.currency == "HKD"

    def test_default_currency(self) -> None:
        fact = ExecutionFact(
            execution_id="EXEC-001",
            order_id="ORD-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="BUY",
            fill_quantity=100,
            fill_price=100.0,
        )
        assert fact.currency == "USD"


# ------------------------------------------------------------------
#  PositionView
# ------------------------------------------------------------------

class TestPositionView:
    def test_long_position(self) -> None:
        view = PositionView(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            quantity=1000,
            average_price=180.0,
            version=3,
        )
        assert view.quantity == 1000
        assert view.side == "LONG"

    def test_short_position(self) -> None:
        view = PositionView(
            position_id="POS-002",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="SHORT",
            quantity=500,
            average_price=180.0,
        )
        assert view.side == "SHORT"

    def test_roundtrip_via_dict(self) -> None:
        view = PositionView(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            quantity=1000,
            average_price=180.0,
            version=3,
            last_updated_at=NOW,
        )
        restored = PositionView.from_dict(view.to_dict())
        assert restored.position_id == view.position_id
        assert restored.quantity == view.quantity
        assert restored.version == 3


# ------------------------------------------------------------------
#  LedgerView
# ------------------------------------------------------------------

class TestLedgerView:
    def test_basic_view(self) -> None:
        view = LedgerView(
            account_id="ACC-001",
            currency="USD",
            trade_amount=180000.0,
            fee_amount=10.0,
            commission_amount=5.0,
            balance=-180015.0,
            version=1,
        )
        assert view.trade_amount == 180000.0
        assert view.fee_amount == 10.0
        assert view.commission_amount == 5.0
        assert view.balance == -180015.0

    def test_roundtrip_via_dict(self) -> None:
        view = LedgerView(
            account_id="ACC-001",
            currency="HKD",
            trade_amount=500000.0,
            balance=-500100.0,
            last_updated_at=NOW,
        )
        restored = LedgerView.from_dict(view.to_dict())
        assert restored.account_id == view.account_id
        assert restored.currency == "HKD"
        assert restored.trade_amount == 500000.0

    def test_default_currency(self) -> None:
        view = LedgerView.from_dict({"account_id": "ACC-001"})
        assert view.currency == "USD"
        assert view.balance == 0.0


# ------------------------------------------------------------------
#  ReconciliationTrigger
# ------------------------------------------------------------------

class TestReconciliationTrigger:
    def test_p0_trigger(self) -> None:
        trigger = ReconciliationTrigger(
            trigger_id="TRIG-001",
            check_id="CHECK-001",
            domain="LEDGER",
            failure_type="ACCOUNTING_IMBALANCE",
            expected_value=180000.0,
            actual_value=0.0,
            delta=-180000.0,
            priority=ReconciliationTriggerPriority.P0,
            auto_repairable=False,
        )
        assert trigger.priority == ReconciliationTriggerPriority.P0
        assert not trigger.auto_repairable

    def test_p2_trigger_auto_repairable(self) -> None:
        trigger = ReconciliationTrigger(
            trigger_id="TRIG-002",
            check_id="CHECK-001",
            domain="POSITION",
            failure_type="POSITION_MISMATCH",
            expected_value=1000.0,
            actual_value=700.0,
            delta=-300.0,
            priority=ReconciliationTriggerPriority.P2,
            auto_repairable=True,
        )
        assert trigger.auto_repairable

    def test_roundtrip_via_dict(self) -> None:
        trigger = ReconciliationTrigger(
            trigger_id="TRIG-001",
            check_id="CHECK-001",
            domain="LEDGER",
            failure_type="LEDGER_AMOUNT_MISMATCH",
            expected_value=180000.0,
            actual_value=179500.0,
            delta=-500.0,
        )
        restored = ReconciliationTrigger.from_dict(trigger.to_dict())
        assert restored.trigger_id == trigger.trigger_id
        assert restored.delta == -500.0


# ------------------------------------------------------------------
#  ConsistencyCheck
# ------------------------------------------------------------------

class TestConsistencyCheck:
    def test_consistent_check(self) -> None:
        check = ConsistencyCheck(
            check_id="CHECK-001",
            account_id="ACC-001",
            instrument_id="NVDA",
        )
        assert check.is_consistent is False  # DEGRADED default
        check.overall_status = ConsistencyDomainStatus.CONSISTENT
        assert check.is_consistent is True

    def test_inconsistent_check(self) -> None:
        check = ConsistencyCheck(
            check_id="CHECK-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            overall_status=ConsistencyDomainStatus.INCONSISTENT,
        )
        assert check.is_inconsistent is True
        assert check.is_consistent is False

    def test_no_triggers_initially(self) -> None:
        check = ConsistencyCheck(
            check_id="CHECK-001",
            account_id="ACC-001",
            instrument_id="NVDA",
        )
        assert not check.has_triggers

    def test_with_snapshots(self) -> None:
        check = ConsistencyCheck(
            check_id="CHECK-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            execution_facts=[
                ExecutionFact(
                    execution_id="EXEC-001",
                    order_id="ORD-001",
                    account_id="ACC-001",
                    instrument_id="NVDA",
                    side="BUY",
                    fill_quantity=1000,
                    fill_price=180.0,
                )
            ],
            position_view=PositionView(
                position_id="POS-001",
                account_id="ACC-001",
                instrument_id="NVDA",
                side="LONG",
                quantity=1000,
            ),
            ledger_view=LedgerView(
                account_id="ACC-001",
                currency="USD",
                trade_amount=180000.0,
            ),
        )
        assert len(check.execution_facts) == 1
        assert check.position_view is not None
        assert check.ledger_view is not None

    def test_roundtrip_via_dict(self) -> None:
        check = ConsistencyCheck(
            check_id="CHECK-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            check_scope="instrument",
            grace_period_ms=5000,
            execution_facts=[
                ExecutionFact(
                    execution_id="EXEC-001",
                    order_id="ORD-001",
                    account_id="ACC-001",
                    instrument_id="NVDA",
                    side="BUY",
                    fill_quantity=1000,
                    fill_price=180.0,
                    occurred_at=NOW,
                )
            ],
            position_view=PositionView(
                position_id="POS-001",
                account_id="ACC-001",
                instrument_id="NVDA",
                side="LONG",
                quantity=1000,
                last_updated_at=NOW,
            ),
            ledger_view=LedgerView(
                account_id="ACC-001",
                currency="USD",
                trade_amount=180000.0,
                last_updated_at=NOW,
            ),
            overall_status=ConsistencyDomainStatus.CONSISTENT,
            correlation_id="CORR-001",
            lineage_id="LINE-001",
            checked_at=NOW,
        )
        # Add a trigger
        check.triggers = [
            ReconciliationTrigger(
                trigger_id="TRIG-001",
                check_id="CHECK-001",
                domain="LEDGER",
                failure_type="LEDGER_AMOUNT_MISMATCH",
                expected_value=180000.0,
                actual_value=179500.0,
                delta=-500.0,
            )
        ]

        restored = ConsistencyCheck.from_dict(check.to_dict())
        assert restored.check_id == check.check_id
        assert restored.account_id == check.account_id
        assert restored.overall_status == ConsistencyDomainStatus.CONSISTENT
        assert len(restored.execution_facts) == 1
        assert restored.execution_facts[0].execution_id == "EXEC-001"
        assert restored.position_view is not None
        assert restored.ledger_view is not None
        assert restored.has_triggers
        assert restored.triggers[0].delta == -500.0
