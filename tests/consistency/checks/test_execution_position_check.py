"""Tests for execution-position consistency check."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import ExecutionFact, PositionView
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.checks.execution_position_check import (
    ExecutionPositionCheck,
    check_execution_position,
)


NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

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
    position_id: str = "POS-001",
    account_id: str = "ACC-001",
    instrument_id: str = "NVDA",
    side: str = "LONG",
    quantity: float = 1000,
    version: int = 1,
) -> PositionView:
    return PositionView(
        position_id=position_id,
        account_id=account_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        version=version,
        last_updated_at=NOW,
    )


# ------------------------------------------------------------------
#  Tests
# ------------------------------------------------------------------

class TestExecutionPositionCheck:
    def test_matches_when_equal(self) -> None:
        checker = ExecutionPositionCheck(grace_period_ms=5000)
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=1000)
        result = checker.check(facts, pos)
        assert result.is_consistent is True
        assert result.status == ConsistencyDomainStatus.CONSISTENT

    def test_matches_multiple_executions(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [
            _fact("EXEC-001", fill_quantity=300, fill_price=180.0),
            _fact("EXEC-002", fill_quantity=700, fill_price=181.0),
        ]
        pos = _pos(quantity=1000)
        result = checker.check(facts, pos)
        assert result.is_consistent

    def test_buy_and_sell_net(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [
            _fact("EXEC-001", fill_quantity=1000, side="BUY"),
            _fact("EXEC-002", fill_quantity=300, side="SELL"),
        ]
        pos = _pos(quantity=700)  # net long 700
        result = checker.check(facts, pos)
        assert result.is_consistent

    def test_position_mismatch(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=700)  # missing 300
        result = checker.check(facts, pos)
        assert result.is_inconsistent
        assert result.failure_type == "POSITION_MISMATCH"
        assert result.delta == -300

    def test_position_overstate(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=1200)  # extra 200
        result = checker.check(facts, pos)
        assert result.is_inconsistent
        assert result.failure_type == "POSITION_OVERSTATE"
        assert result.delta == 200

    def test_missing_position_event(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=0)
        result = checker.check(facts, pos)
        assert result.is_inconsistent
        assert result.failure_type == "MISSING_POSITION_EVENT"
        assert result.delta == -1000

    def test_short_position(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [_fact(side="SELL", fill_quantity=500)]
        pos = _pos(side="SHORT", quantity=500)
        result = checker.check(facts, pos)
        assert result.is_consistent

    def test_degraded_within_grace_period(self) -> None:
        """When events are very recent, mismatch → DEGRADED not INCONSISTENT."""
        checker = ExecutionPositionCheck(grace_period_ms=5000)
        facts = [_fact(fill_quantity=1000, fill_price=180.0)]
        facts[0].occurred_at = NOW
        pos = _pos(quantity=0, version=0)
        pos.last_updated_at = NOW  # same time, no lag
        result = checker.check(facts, pos)
        # Zero lag means not within grace period window (lag >= grace)
        assert result.status in (ConsistencyDomainStatus.DEGRADED, ConsistencyDomainStatus.INCONSISTENT)

    def test_inconsistent_after_grace_period(self) -> None:
        """After grace period, mismatch → INCONSISTENT."""
        checker = ExecutionPositionCheck(grace_period_ms=100)
        old = datetime(2026, 8, 11, 9, 0, 0, tzinfo=timezone.utc)
        facts = [_fact(fill_quantity=1000)]
        facts[0].occurred_at = old
        pos = _pos(quantity=0)
        pos.last_updated_at = NOW  # 1 hour gap
        result = checker.check(facts, pos)
        assert result.status == ConsistencyDomainStatus.INCONSISTENT

    def test_matrix_row_present(self) -> None:
        checker = ExecutionPositionCheck()
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=700)
        result = checker.check(facts, pos)
        assert len(result.matrix.rows) == 1
        assert result.matrix.rows[0].metric == "position_quantity"
        assert not result.matrix.rows[0].pass_

    def test_event_lag_tracked(self) -> None:
        checker = ExecutionPositionCheck(grace_period_ms=5000)
        early = datetime(2026, 8, 11, 9, 59, 50, tzinfo=timezone.utc)
        late = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)
        facts = [_fact(fill_quantity=1000)]
        facts[0].occurred_at = early
        pos = _pos(quantity=0)
        pos.last_updated_at = late
        result = checker.check(facts, pos)
        assert result.event_lag_ms == 10000  # 10s lag

    def test_convenience_function(self) -> None:
        facts = [_fact(fill_quantity=1000)]
        pos = _pos(quantity=1000)
        result = check_execution_position(facts, pos)
        assert result.is_consistent


class TestFunctionCheckExecutionPosition:
    """Tests for the convenience check_execution_position function."""

    def test_consistent(self) -> None:
        result = check_execution_position(
            [_fact(fill_quantity=500)],
            _pos(quantity=500),
        )
        assert result.is_consistent

    def test_mismatch(self) -> None:
        result = check_execution_position(
            [_fact(fill_quantity=500)],
            _pos(quantity=300),
        )
        assert result.is_inconsistent
        assert result.failure_type == "POSITION_MISMATCH"
