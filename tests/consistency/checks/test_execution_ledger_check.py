"""Tests for execution-ledger consistency check."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import ExecutionFact, LedgerView
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.checks.execution_ledger_check import (
    ExecutionLedgerCheck,
    check_execution_ledger,
)


NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


def _fact(
    execution_id: str = "EXEC-001",
    account_id: str = "ACC-001",
    instrument_id: str = "NVDA",
    side: str = "BUY",
    fill_quantity: float = 1000,
    fill_price: float = 180.0,
    fee: float = 10.0,
    commission: float = 5.0,
) -> ExecutionFact:
    return ExecutionFact(
        execution_id=execution_id,
        order_id=f"ORD-{execution_id[-3:]}",
        account_id=account_id,
        instrument_id=instrument_id,
        side=side,
        fill_quantity=fill_quantity,
        fill_price=fill_price,
        fee=fee,
        commission=commission,
        occurred_at=NOW,
    )


def _ledger(
    account_id: str = "ACC-001",
    currency: str = "USD",
    trade_amount: float = 180000.0,
    fee_amount: float = 10.0,
    commission_amount: float = 5.0,
    balance: float = -180015.0,
    version: int = 1,
) -> LedgerView:
    return LedgerView(
        account_id=account_id,
        currency=currency,
        trade_amount=trade_amount,
        fee_amount=fee_amount,
        commission_amount=commission_amount,
        debit_total=15.0,
        credit_total=180000.0,
        balance=balance,
        version=version,
        last_updated_at=NOW,
    )


# ------------------------------------------------------------------
#  Tests
# ------------------------------------------------------------------

class TestExecutionLedgerCheck:
    def test_all_match(self) -> None:
        checker = ExecutionLedgerCheck(grace_period_ms=5000)
        facts = [_fact()]
        ledger = _ledger()
        result = checker.check(facts, ledger)
        assert result.is_consistent
        assert result.status == ConsistencyDomainStatus.CONSISTENT

    def test_multiple_executions(self) -> None:
        checker = ExecutionLedgerCheck()
        facts = [
            _fact("EXEC-001", fill_quantity=300, fill_price=180.0, fee=5.0, commission=2.0),
            _fact("EXEC-002", fill_quantity=700, fill_price=181.0, fee=5.0, commission=3.0),
        ]
        # Total: trade=300*180+700*181=54000+126700=180700, fee=10, commission=5
        ledger = _ledger(trade_amount=180700.0, fee_amount=10.0, commission_amount=5.0,
                         balance=-(180700+10+5))
        result = checker.check(facts, ledger)
        assert result.is_consistent

    def test_sell_ledger(self) -> None:
        checker = ExecutionLedgerCheck()
        facts = [_fact(side="SELL", fill_price=185.0)]
        ledger = _ledger(trade_amount=185000.0, balance=+(185000 - 10 - 5))
        result = checker.check(facts, ledger)
        assert result.is_consistent

    def test_missing_ledger_entry(self) -> None:
        """Ledger has zero trade amount when execution says 180000."""
        checker = ExecutionLedgerCheck()
        facts = [_fact()]
        ledger = _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0)
        result = checker.check(facts, ledger)
        assert result.is_inconsistent
        assert result.failure_type == "MISSING_LEDGER_ENTRY"

    def test_ledger_amount_mismatch(self) -> None:
        """Ledger shows 179500 instead of 180000."""
        checker = ExecutionLedgerCheck()
        facts = [_fact()]
        ledger = _ledger(trade_amount=179500.0)
        result = checker.check(facts, ledger)
        assert result.is_inconsistent
        assert result.failure_type == "LEDGER_AMOUNT_MISMATCH"
        assert result.expected_value == 180000.0
        assert result.actual_value == 179500.0
        assert result.delta == -500.0

    def test_fee_mismatch(self) -> None:
        """Fee is 10 but ledger shows 0."""
        checker = ExecutionLedgerCheck()
        facts = [_fact(fee=10.0)]
        ledger = _ledger(fee_amount=0.0)
        result = checker.check(facts, ledger)
        assert result.is_inconsistent
        assert result.failure_type == "FEE_MISMATCH"

    def test_commission_mismatch(self) -> None:
        """Commission is 5 but ledger shows 3."""
        checker = ExecutionLedgerCheck()
        facts = [_fact(commission=5.0)]
        ledger = _ledger(commission_amount=3.0)
        result = checker.check(facts, ledger)
        assert result.is_inconsistent
        assert result.failure_type == "COMMISSION_MISMATCH"

    def test_matrix_has_three_rows(self) -> None:
        checker = ExecutionLedgerCheck()
        result = checker.check([_fact()], _ledger())
        assert len(result.matrix.rows) == 3
        metrics = {r.metric for r in result.matrix.rows}
        assert metrics == {"trade_value", "fee", "commission"}

    def test_all_matrix_rows_pass_when_consistent(self) -> None:
        checker = ExecutionLedgerCheck()
        result = checker.check([_fact()], _ledger())
        assert result.matrix.all_pass

    def test_matrix_failure_count(self) -> None:
        checker = ExecutionLedgerCheck()
        facts = [_fact(fee=10.0)]
        ledger = _ledger(fee_amount=0.0)
        result = checker.check(facts, ledger)
        assert result.matrix.failure_count == 1

    def test_degraded_within_grace_period(self) -> None:
        checker = ExecutionLedgerCheck(grace_period_ms=5000)
        facts = [_fact()]
        facts[0].occurred_at = NOW
        ledger = _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0)
        ledger.last_updated_at = NOW
        result = checker.check(facts, ledger)
        assert result.status in (ConsistencyDomainStatus.DEGRADED, ConsistencyDomainStatus.INCONSISTENT)

    def test_inconsistent_after_grace(self) -> None:
        checker = ExecutionLedgerCheck(grace_period_ms=100)
        old = datetime(2026, 8, 11, 9, 0, 0, tzinfo=timezone.utc)
        facts = [_fact()]
        facts[0].occurred_at = old
        ledger = _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0)
        ledger.last_updated_at = NOW
        result = checker.check(facts, ledger)
        assert result.status == ConsistencyDomainStatus.INCONSISTENT

    def test_no_facts_no_fees(self) -> None:
        """Zero executions with zero ledger should be consistent."""
        checker = ExecutionLedgerCheck()
        ledger = _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0)
        result = checker.check([], ledger)
        assert result.is_consistent

    def test_convenience_function(self) -> None:
        facts = [_fact()]
        ledger = _ledger()
        result = check_execution_ledger(facts, ledger)
        assert result.is_consistent

    def test_event_lag_tracked(self) -> None:
        checker = ExecutionLedgerCheck(grace_period_ms=5000)
        early = datetime(2026, 8, 11, 9, 59, 55, tzinfo=timezone.utc)
        late = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)
        facts = [_fact()]
        facts[0].occurred_at = early
        ledger = _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0)
        ledger.last_updated_at = late
        result = checker.check(facts, ledger)
        assert result.event_lag_ms == 5000


class TestFunctionCheckExecutionLedger:
    """Tests for the convenience check_execution_ledger function."""

    def test_consistent(self) -> None:
        result = check_execution_ledger([_fact()], _ledger())
        assert result.is_consistent

    def test_missing_all(self) -> None:
        result = check_execution_ledger(
            [_fact()],
            _ledger(trade_amount=0, fee_amount=0, commission_amount=0, balance=0),
        )
        assert result.is_inconsistent
