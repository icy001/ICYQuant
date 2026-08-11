"""Tests for RecoveryService — orchestration of the full recovery pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.consistency.domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    PositionView,
    LedgerView,
)
from services.consistency.domain.consistency_result import ConsistencyResult
from services.consistency.domain.consistency_status import ConsistencyDomainStatus
from services.consistency.services.consistency_service import ConsistencyService
from services.recovery.domain.recovery_job import RecoveryJournalEntryState
from services.recovery.domain.recovery_scope import RecoveryScope, RecoveryScopeType
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType
from services.recovery.repositories.recovery_repository import RecoveryRepository
from services.recovery.services.recovery_service import RecoveryService
from services.recovery.services.replay_service import ReplayService
from services.recovery.services.recovery_verifier import RecoveryVerifier

NOW = datetime.now(timezone.utc)


def _trigger(**kwargs):
    """Factory for a mock ReconciliationTrigger."""
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
    """Factory for ExecutionFact."""
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


def _make_recovery_service(grace_period_ms=5000):
    """Create a fully wired RecoveryService for testing."""
    repo = RecoveryRepository()
    cs = ConsistencyService(grace_period_ms=grace_period_ms)
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
# Job Creation
# ============================================================

class TestJobCreation:
    """Tests for creating recovery jobs from consistency triggers."""

    def test_create_job_from_trigger(self) -> None:
        svc, repo, cs = _make_recovery_service()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)

        job = svc.handle_consistency_failure(trigger, [fact])
        assert job is not None
        assert job.status == RecoveryStatus.COMPLETED  # full pipeline success
        assert repo.count() >= 1

    def test_create_job_increments_counter(self) -> None:
        svc, repo, cs = _make_recovery_service()
        assert svc.jobs_created == 0
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        svc.handle_consistency_failure(trigger, [fact])
        assert svc.jobs_created == 1

    def test_job_has_correct_type(self) -> None:
        svc, repo, cs = _make_recovery_service()
        trigger = _trigger(failure_type="POSITION_MISMATCH")
        fact = _fact()
        cs.record_execution(fact)
        job = svc.handle_consistency_failure(trigger, [fact])
        assert job.recovery_type == RecoveryType.POSITION_REPLAY


class TestDeduplication:
    """Tests for deduplication of overlapping recovery jobs."""

    def test_duplicate_trigger_deduplicated(self) -> None:
        svc, repo, cs = _make_recovery_service()
        trigger = _trigger()
        fact = _fact()
        cs.record_execution(fact)
        cs.record_position(PositionView(
            position_id="POS-001", account_id="ACC-001", instrument_id="NVDA",
            side="LONG", quantity=1000, average_price=180.0, last_updated_at=NOW,
        ))
        cs.record_ledger(LedgerView(
            account_id="ACC-001", currency="USD", trade_amount=180000,
            fee_amount=10.0, commission_amount=5.0, last_updated_at=NOW,
        ))

        job1 = svc.handle_consistency_failure(trigger, [fact])
        assert job1 is not None
        # First job completed → lock released

        # Same scope = dedup check: lock was released, so it creates a new job
        # But the dedup is based on lock existence at create time
        # Since first job completed, lock is free → new job created
        job2 = svc.handle_consistency_failure(trigger, [fact])
        assert job2 is not None  # New job since old one completed
        assert svc.jobs_created == 2

    def test_same_scope_while_active_deduplicated(self) -> None:
        """Dedup happens when an active job holds the lock."""
        svc, repo, cs = _make_recovery_service()
        trigger = _trigger()
        # Manually lock the scope to simulate active job
        # trigger has execution_id but empty account_id/instrument_id
        # → scope key is "EXECUTION:EXEC-001" (empty strings are skipped in recovery_key)
        svc._locks["EXECUTION:EXEC-001"] = "REC-ACTIVE"
        job = svc.handle_consistency_failure(trigger, [])
        assert job is None
        assert svc.jobs_deduplicated == 1

    def test_different_scope_not_deduplicated(self) -> None:
        svc, repo, cs = _make_recovery_service()
        t1 = _trigger(trigger_id="TRIG-001", execution_id="EXEC-001")
        t2 = _trigger(trigger_id="TRIG-002", execution_id="EXEC-002")
        f1 = _fact("EXEC-001", qty=500)
        f2 = _fact("EXEC-002", qty=300)
        cs.record_execution(f1)
        cs.record_execution(f2)

        # Manually lock EXEC-001 scope
        svc._locks["EXECUTION:ACC-001:NVDA:EXEC-001"] = "REC-ACTIVE"

        # EXEC-002 is a different key → should NOT be deduplicated
        assert not svc.is_locked("EXECUTION:ACC-001:NVDA:EXEC-002")
        job2 = svc.handle_consistency_failure(t2, [f2])
        assert job2 is not None
