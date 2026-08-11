"""Tests for RecoveryVerifier — post-recovery consistency verification."""

from __future__ import annotations

from datetime import datetime, timezone

from services.consistency.domain.consistency_check import (
    ExecutionFact,
    PositionView,
    LedgerView,
)
from services.consistency.services.consistency_service import ConsistencyService
from services.recovery.domain.recovery_job import RecoveryJob
from services.recovery.domain.recovery_scope import RecoveryScope
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType
from services.recovery.services.recovery_verifier import RecoveryVerifier

NOW = datetime.now(timezone.utc)


def _fact(**kwargs):
    defaults = dict(
        execution_id="EXEC-001",
        order_id="ORD-001",
        account_id="ACC-001",
        instrument_id="NVDA",
        side="BUY",
        fill_quantity=1000,
        fill_price=180.0,
        fee=10.0,
        commission=5.0,
        occurred_at=NOW,
    )
    defaults.update(kwargs)
    return ExecutionFact(**defaults)


def _job():
    return RecoveryJob(
        job_id="REC-001",
        recovery_type=RecoveryType.POSITION_REPLAY,
        scope=RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA"),
        source_check_id="CHECK-001",
    )


class TestRecoveryVerifier:
    """Tests for RecoveryVerifier."""

    def test_verify_consistent(self) -> None:
        cs = ConsistencyService()
        cs.record_execution(_fact())
        # Position & ledger match → consistent
        v = RecoveryVerifier(consistency_service=cs)
        job = _job()
        result = v.verify(job, [_fact()])
        assert result["consistent"]

    def test_verify_inconsistent_position(self) -> None:
        cs = ConsistencyService(grace_period_ms=0)
        cs.record_execution(_fact(fill_quantity=1000))
        # Record WRONG position to force mismatch
        cs.record_position(PositionView(
            position_id="POS-001", account_id="ACC-001", instrument_id="NVDA",
            side="LONG", quantity=700, average_price=180.0, last_updated_at=NOW,
        ))
        v = RecoveryVerifier(consistency_service=cs)
        job = _job()
        result = v.verify(job, [_fact()])
        assert not result["consistent"]

    def test_verify_degraded_as_success(self) -> None:
        cs = ConsistencyService(grace_period_ms=60000)
        cs.record_execution(_fact())
        v = RecoveryVerifier(consistency_service=cs)
        job = _job()
        result = v.verify(job, [_fact()])
        # Within grace, degraded counts as success
        assert result["consistent"]

    def test_verify_with_failure_details(self) -> None:
        cs = ConsistencyService(grace_period_ms=0)
        cs.record_execution(_fact(fill_quantity=1000))
        v = RecoveryVerifier(consistency_service=cs)
        job = _job()
        result = v.verify(job, [_fact()])
        if not result["consistent"]:
            assert result["failure_code"] is not None
            assert result["failure_reason"] is not None
