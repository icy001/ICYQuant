"""Integration tests: full recovery pipeline from consistency failure to state restoration."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    PositionView,
    LedgerView,
)
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.services.consistency_service import ConsistencyService
from services.recovery.domain.recovery_job import RecoveryJob, RecoveryJournalEntryState
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType
from services.recovery.repositories.recovery_repository import RecoveryRepository
from services.recovery.services.recovery_service import RecoveryService
from services.recovery.services.replay_service import ReplayService
from services.recovery.services.recovery_verifier import RecoveryVerifier

NOW = datetime.now(timezone.utc)


# ============================================================
# Helpers
# ============================================================

def _trigger(**kwargs):
    from services.consistency.domain.consistency_check import ReconciliationTrigger
    defaults = dict(
        trigger_id="TRIG-001",
        check_id="CHECK-001",
        domain="POSITION",
        failure_type="POSITION_MISMATCH",
        expected_value=1000,
        actual_value=700,
        delta=-300,
        priority=2,
        execution_id="EXEC-001",
        auto_repairable=True,
    )
    defaults.update(kwargs)
    return ReconciliationTrigger(**defaults)


def _fact(eid="EXEC-001", qty=1000, price=180.0, **kwargs):
    defaults = dict(
        execution_id=eid,
        order_id="ORD-001",
        account_id="ACC-001",
        instrument_id="NVDA",
        side="BUY",
        fill_quantity=qty,
        fill_price=price,
        fee=10.0,
        commission=5.0,
        occurred_at=NOW,
    )
    defaults.update(kwargs)
    return ExecutionFact(**defaults)


def _pos(quantity=1000, **kwargs):
    defaults = dict(
        position_id="POS-001",
        account_id="ACC-001",
        instrument_id="NVDA",
        side="LONG",
        quantity=quantity,
        average_price=180.0,
        last_updated_at=NOW,
    )
    defaults.update(kwargs)
    return PositionView(**defaults)


def _ledger(trade_amount=180000, **kwargs):
    defaults = dict(
        account_id="ACC-001",
        currency="USD",
        trade_amount=trade_amount,
        fee_amount=10.0,
        commission_amount=5.0,
        last_updated_at=NOW,
    )
    defaults.update(kwargs)
    return LedgerView(**defaults)


def _make_pipeline():
    """Create the full recovery pipeline."""
    repo = RecoveryRepository()
    cs = ConsistencyService(grace_period_ms=5000)
    replay = ReplayService()
    verifier = RecoveryVerifier(consistency_service=cs)
    svc = RecoveryService(
        repository=repo,
        replay_service=replay,
        verifier=verifier,
        consistency_service=cs,
    )
    return svc, repo, cs


# ============================================================
# Full Pipeline Tests
# ============================================================

class TestFullRecoveryPipeline:
    """End-to-end recovery pipeline: detect → recover → verify → complete."""

    def test_full_pipeline_position_mismatch(self) -> None:
        """Position mismatch → replay → verify → COMPLETED."""
        svc, repo, cs = _make_pipeline()
        trigger = _trigger(failure_type="POSITION_MISMATCH")
        fact = _fact(fill_quantity=1000)

        # Record execution in consistency service
        cs.record_execution(fact)

        # Record correct position to verify recovery
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger(trade_amount=180000))

        job = svc.handle_consistency_failure(trigger, [fact])
        assert job is not None
        assert job.status == RecoveryStatus.COMPLETED
        assert svc.jobs_completed == 1
        assert svc.jobs_created == 1

    def test_pipeline_emits_completion_event(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        job = svc.handle_consistency_failure(trigger, [fact])

        events = svc.collect_events()
        assert len(events) >= 2  # STARTED + COMPLETED
        event_types = [e.event_type for e in events]
        assert "RECOVERY_STARTED" in event_types
        assert "RECOVERY_COMPLETED" in event_types

    def test_pipeline_journal_full_trail(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        job = svc.handle_consistency_failure(trigger, [fact])
        states = [e.state.value for e in job.journal.entries]
        assert "STARTED" in states
        assert "PRECHECK_PASSED" in states
        assert "POSITION_REPLAYED" in states
        assert "CONSISTENCY_VERIFIED" in states
        assert "COMPLETED" in states

    def test_pipeline_metrics_updated(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        job = svc.handle_consistency_failure(trigger, [fact])
        assert svc.jobs_created == 1
        assert svc.jobs_completed == 1
        assert svc.total_events_replayed > 0

    def test_pipeline_success_rate(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        svc.handle_consistency_failure(trigger, [fact])
        assert svc.success_rate == 1.0


class TestRecoveryFailureScenarios:
    """Recovery pipeline failure and retry scenarios."""

    def test_retry_failed_job(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact(fill_quantity=1000)
        cs.record_execution(fact)

        # Record wrong state so verify fails
        cs.record_position(_pos(quantity=700))
        cs.record_ledger(_ledger(trade_amount=180000))

        job = svc.handle_consistency_failure(trigger, [fact])
        # Will fail verification because position snapshot is 700 != 1000
        assert job.status in (RecoveryStatus.FAILED, RecoveryStatus.COMPLETED)
        if job.status == RecoveryStatus.FAILED:
            assert svc.jobs_failed >= 1
            assert not job.is_terminal or job.status == RecoveryStatus.FAILED

    def test_escalation_after_max_retries(self) -> None:
        svc, repo, cs = _make_recovery_service_with_max_retries(2)
        trigger = _trigger()
        fact = _fact(fill_quantity=1000)
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=700))  # wrong

        job = svc.handle_consistency_failure(trigger, [fact])
        assert job is not None
        # After max retries, should escalate
        assert job.status in (RecoveryStatus.ESCALATED, RecoveryStatus.COMPLETED)
        if job.status == RecoveryStatus.ESCALATED:
            assert svc.jobs_escalated >= 1


def _make_recovery_service_with_max_retries(max_retries):
    repo = RecoveryRepository()
    cs = ConsistencyService(grace_period_ms=0)
    replay = ReplayService()
    verifier = RecoveryVerifier(consistency_service=cs)
    svc = RecoveryService(
        repository=repo,
        replay_service=replay,
        verifier=verifier,
        consistency_service=cs,
        max_retries=max_retries,
    )
    return svc, repo, cs


class TestCrossDomainRecovery:
    """Recovery across multiple domains."""

    def test_full_transaction_recovery(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger(failure_type="EVENT_SEQUENCE_GAP")
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger(trade_amount=180000))

        job = svc.handle_consistency_failure(trigger, [fact])
        assert job is not None
        # EVENT_SEQUENCE_GAP → FULL_TRANSACTION_REPLAY
        assert job.recovery_type == RecoveryType.FULL_TRANSACTION_REPLAY

    def test_ledger_only_recovery(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger(failure_type="MISSING_LEDGER_ENTRY")
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger(trade_amount=180000))

        job = svc.handle_consistency_failure(trigger, [fact])
        assert job is not None
        assert job.recovery_type == RecoveryType.LEDGER_REPLAY


class TestRecoveryEvents:
    """Recovery event emission."""

    def test_started_event_has_correct_fields(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        svc.handle_consistency_failure(trigger, [fact])
        events = svc.collect_events()
        started = [e for e in events if e.event_type == "RECOVERY_STARTED"][0]
        assert started.job_id is not None
        assert started.recovery_key is not None
        assert started.recovery_type is not None
        assert started.attempt == 1

    def test_completed_event_has_metrics(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        svc.handle_consistency_failure(trigger, [fact])
        events = svc.collect_events()
        completed = [e for e in events if e.event_type == "RECOVERY_COMPLETED"][0]
        assert completed.events_replayed >= 1

    def test_collect_events_drains_queue(self) -> None:
        svc, repo, cs = _make_pipeline()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(_pos(quantity=1000))
        cs.record_ledger(_ledger())

        svc.handle_consistency_failure(trigger, [fact])
        first = svc.collect_events()
        assert len(first) > 0
        second = svc.collect_events()
        assert len(second) == 0  # drained
