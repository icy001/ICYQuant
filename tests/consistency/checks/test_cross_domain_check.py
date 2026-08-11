"""Tests for cross-domain consistency check."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import ExecutionFact, LedgerView, PositionView
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.checks.cross_domain_check import CrossDomainCheck


NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


def _fact(
    execution_id: str = "EXEC-001",
    account_id: str = "ACC-001",
    side: str = "BUY",
    fill_quantity: float = 1000,
    fill_price: float = 180.0,
) -> ExecutionFact:
    return ExecutionFact(
        execution_id=execution_id,
        order_id=f"ORD-{execution_id[-3:]}",
        account_id=account_id,
        instrument_id="NVDA",
        side=side,
        fill_quantity=fill_quantity,
        fill_price=fill_price,
        occurred_at=NOW,
    )


def _pos(quantity: float = 1000) -> PositionView:
    return PositionView(
        position_id="POS-001",
        account_id="ACC-001",
        instrument_id="NVDA",
        side="LONG",
        quantity=quantity,
        version=1,
        last_updated_at=NOW,
    )


def _ledger(trade_amount: float = 180000.0) -> LedgerView:
    return LedgerView(
        account_id="ACC-001",
        currency="USD",
        trade_amount=trade_amount,
        last_updated_at=NOW,
    )


class TestCrossDomainCheck:
    def test_both_consistent(self) -> None:
        checker = CrossDomainCheck(grace_period_ms=5000)
        facts = [_fact()]
        pos = _pos(1000)
        ledger = _ledger(180000.0)
        check = checker.check(facts, pos, ledger)
        assert check.overall_status == ConsistencyDomainStatus.CONSISTENT
        assert check.is_consistent

    def test_position_mismatch(self) -> None:
        checker = CrossDomainCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(700)  # mismatch
        ledger = _ledger(180000.0)
        check = checker.check(facts, pos, ledger)
        assert check.overall_status == ConsistencyDomainStatus.INCONSISTENT
        assert len(check.results) == 2
        assert check.results[0].domain == "POSITION"
        assert check.results[0].is_inconsistent

    def test_ledger_mismatch(self) -> None:
        checker = CrossDomainCheck()
        facts = [_fact()]
        pos = _pos(1000)
        ledger = _ledger(0.0)  # missing
        check = checker.check(facts, pos, ledger)
        assert check.overall_status == ConsistencyDomainStatus.INCONSISTENT
        assert check.results[1].domain == "LEDGER"
        assert check.results[1].is_inconsistent

    def test_both_mismatch(self) -> None:
        checker = CrossDomainCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(500)
        ledger = _ledger(0.0)
        check = checker.check(facts, pos, ledger)
        assert check.overall_status == ConsistencyDomainStatus.INCONSISTENT
        assert check.results[0].is_inconsistent
        assert check.results[1].is_inconsistent

    def test_partial_multiple_executions(self) -> None:
        checker = CrossDomainCheck()
        facts = [
            _fact("EXEC-001", fill_quantity=300, fill_price=180.0),
            _fact("EXEC-002", fill_quantity=700, fill_price=181.0),
        ]
        pos = _pos(1000)
        ledger = _ledger(300 * 180 + 700 * 181)  # 54000 + 126700 = 180700
        check = checker.check(facts, pos, ledger)
        assert check.overall_status == ConsistencyDomainStatus.CONSISTENT

    def test_snapshots_preserved(self) -> None:
        checker = CrossDomainCheck()
        facts = [_fact()]
        pos = _pos(1000)
        ledger = _ledger(180000.0)
        check = checker.check(facts, pos, ledger)
        assert len(check.execution_facts) == 1
        assert check.position_view is not None
        assert check.ledger_view is not None
        assert check.position_view.quantity == 1000
        assert check.ledger_view.trade_amount == 180000.0

    def test_degraded_when_position_lag(self) -> None:
        """Recent event with position lag → both may be degraded."""
        checker = CrossDomainCheck(grace_period_ms=5000)
        facts = [_fact(fill_quantity=1000)]
        facts[0].occurred_at = NOW
        pos = _pos(quantity=0)
        pos.last_updated_at = NOW
        ledger = _ledger(trade_amount=0.0)
        ledger.last_updated_at = NOW
        check = checker.check(facts, pos, ledger)
        # All at same time → not within grace for inconsistency
        assert check.overall_status in (
            ConsistencyDomainStatus.DEGRADED,
            ConsistencyDomainStatus.INCONSISTENT,
        )
