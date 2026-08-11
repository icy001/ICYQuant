"""Tests for ReplayService — deterministic event replay."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import ExecutionFact
from services.recovery.domain.recovery_job import RecoveryJob, RecoveryPlan
from services.recovery.domain.recovery_scope import RecoveryScope
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType
from services.recovery.services.replay_service import ReplayService

NOW = datetime.now(timezone.utc)


def _fact(eid="EXEC-001", seq=None, qty=1000, price=180.0, **kwargs):
    # Pop override kwargs that would collide with explicit defaults
    order_id = kwargs.pop("order_id", "ORD-001")
    account_id = kwargs.pop("account_id", "ACC-001")
    instrument_id = kwargs.pop("instrument_id", "NVDA")
    occurred_at = kwargs.pop("occurred_at", NOW)
    fact = ExecutionFact(
        execution_id=eid,
        order_id=order_id,
        account_id=account_id,
        instrument_id=instrument_id,
        side="BUY",
        fill_quantity=qty,
        fill_price=price,
        fee=10.0,
        commission=5.0,
        occurred_at=occurred_at,
        **kwargs,
    )
    if seq is not None:
        fact.sequence_number = seq
    return fact


def _job(recovery_type=RecoveryType.POSITION_REPLAY):
    return RecoveryJob(
        job_id="REC-001",
        recovery_type=recovery_type,
        scope=RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA"),
        source_check_id="CHECK-001",
    )


class TestReplayService:
    """Tests for ReplayService core."""

    def test_replay_success_no_handler(self) -> None:
        """Replay without handlers should succeed (no-op)."""
        svc = ReplayService()
        facts = [_fact("EXEC-001")]
        job = _job()
        result = svc.replay(job, facts)
        assert result["success"]
        assert result["events_replayed"] == 1
        assert result["events_loaded"] == 1

    def test_replay_multiple_facts(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001"), _fact("EXEC-002"), _fact("EXEC-003")]
        job = _job()
        result = svc.replay(job, facts)
        assert result["success"]
        assert result["events_replayed"] == 3

    def test_replay_sorts_by_sequence(self) -> None:
        svc = ReplayService()
        facts = [
            _fact("EXEC-003", seq=3, qty=300),
            _fact("EXEC-001", seq=1, qty=100),
            _fact("EXEC-002", seq=2, qty=200),
        ]
        sorted_facts = svc._sort_by_sequence(facts)
        assert [f.execution_id for f in sorted_facts] == ["EXEC-001", "EXEC-002", "EXEC-003"]

    def test_replay_sorts_by_occurred_at_fallback(self) -> None:
        svc = ReplayService()
        t1 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 8, 1, 10, 0, 1, tzinfo=timezone.utc)
        t3 = datetime(2026, 8, 1, 10, 0, 2, tzinfo=timezone.utc)
        facts = [
            _fact("EXEC-002", occurred_at=t2),
            _fact("EXEC-001", occurred_at=t1),
            _fact("EXEC-003", occurred_at=t3),
        ]
        sorted_facts = svc._sort_by_sequence(facts)
        assert [f.execution_id for f in sorted_facts] == ["EXEC-001", "EXEC-002", "EXEC-003"]

    def test_replay_position_type(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001")]
        job = _job(RecoveryType.POSITION_REPLAY)
        result = svc.replay(job, facts)
        assert result["success"]
        assert result["events_replayed"] == 1

    def test_replay_ledger_type(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001")]
        job = _job(RecoveryType.LEDGER_REPLAY)
        result = svc.replay(job, facts)
        assert result["success"]
        assert result["events_replayed"] == 1

    def test_replay_full_transaction(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001")]
        job = _job(RecoveryType.FULL_TRANSACTION_REPLAY)
        result = svc.replay(job, facts)
        assert result["success"]
        assert result["events_replayed"] == 1

    def test_replay_empty_facts(self) -> None:
        svc = ReplayService()
        job = _job()
        result = svc.replay(job, [])
        assert result["success"]
        assert result["events_replayed"] == 0


class TestReplayScope:
    """Tests for scope-based replay filtering."""

    def test_filter_by_execution(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001"), _fact("EXEC-002"), _fact("EXEC-003")]
        scope = RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA")
        filtered = svc._filter_by_scope(facts, scope)
        assert len(filtered) == 1
        assert filtered[0].execution_id == "EXEC-001"

    def test_filter_by_account(self) -> None:
        svc = ReplayService()
        facts = [
            _fact("EXEC-001", account_id="ACC-001"),
            _fact("EXEC-002", account_id="ACC-001"),
            _fact("EXEC-003", account_id="ACC-002"),
        ]
        scope = RecoveryScope.for_account("ACC-001")
        filtered = svc._filter_by_scope(facts, scope)
        assert len(filtered) == 2

    def test_filter_by_instrument(self) -> None:
        svc = ReplayService()
        facts = [
            _fact("EXEC-001", account_id="ACC-001", instrument_id="NVDA"),
            _fact("EXEC-002", account_id="ACC-001", instrument_id="AAPL"),
            _fact("EXEC-003", account_id="ACC-001", instrument_id="NVDA"),
        ]
        scope = RecoveryScope.for_instrument("ACC-001", "NVDA")
        filtered = svc._filter_by_scope(facts, scope)
        assert len(filtered) == 2

    def test_filter_by_order(self) -> None:
        svc = ReplayService()
        facts = [
            _fact("EXEC-001", order_id="ORD-001"),
            _fact("EXEC-002", order_id="ORD-001"),
            _fact("EXEC-003", order_id="ORD-002"),
        ]
        scope = RecoveryScope.for_order("ORD-001", "ACC-001", "NVDA")
        filtered = svc._filter_by_scope(facts, scope)
        assert len(filtered) == 2

    def test_replay_scope_method(self) -> None:
        svc = ReplayService()
        facts = [_fact("EXEC-001"), _fact("EXEC-002")]
        scope = RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA")
        filtered = svc.replay_scope(facts, scope)
        assert len(filtered) == 1
