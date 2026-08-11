"""Tests for RecoveryJob, RecoveryPlan, RecoveryJournal, RecoveryScope."""

from __future__ import annotations

from datetime import datetime, timezone

from services.recovery.domain.recovery_job import (
    RecoveryJob,
    RecoveryJournal,
    RecoveryJournalEntry,
    RecoveryJournalEntryState,
    RecoveryPlan,
)
from services.recovery.domain.recovery_scope import RecoveryScope, RecoveryScopeType
from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType

NOW = datetime.now(timezone.utc)


# ============================================================
# RecoveryScope
# ============================================================

class TestRecoveryScope:
    """Tests for RecoveryScope value object."""

    def test_for_execution(self) -> None:
        scope = RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA")
        assert scope.scope_type == RecoveryScopeType.EXECUTION
        assert scope.execution_id == "EXEC-001"
        assert scope.account_id == "ACC-001"
        assert scope.instrument_id == "NVDA"

    def test_recovery_key_execution(self) -> None:
        scope = RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA")
        assert scope.recovery_key == "EXECUTION:ACC-001:NVDA:EXEC-001"

    def test_recovery_key_order(self) -> None:
        scope = RecoveryScope.for_order("ORD-001", "ACC-001", "NVDA")
        assert scope.recovery_key == "ORDER:ACC-001:NVDA:ORD-001"

    def test_recovery_key_account(self) -> None:
        scope = RecoveryScope.for_account("ACC-001")
        assert scope.recovery_key == "ACCOUNT:ACC-001"

    def test_recovery_key_instrument(self) -> None:
        scope = RecoveryScope.for_instrument("ACC-001", "NVDA")
        assert scope.recovery_key == "INSTRUMENT:ACC-001:NVDA"

    def test_to_dict_roundtrip(self) -> None:
        scope = RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA")
        data = scope.to_dict()
        restored = RecoveryScope.from_dict(data)
        assert restored.scope_type == scope.scope_type
        assert restored.execution_id == scope.execution_id
        assert restored.recovery_key == scope.recovery_key


# ============================================================
# RecoveryPlan
# ============================================================

class TestRecoveryPlan:
    """Tests for RecoveryPlan."""

    def test_full_replay_plan(self) -> None:
        plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="REPLAY_REQUIRED",
            projection_action="REBUILD_REQUIRED",
            reason="MISSING_LEDGER_ENTRY",
        )
        assert plan.requires_position_replay
        assert plan.requires_ledger_replay
        assert plan.requires_projection_rebuild
        assert plan.precheck_passed  # no checks yet = passed

    def test_position_only_plan(self) -> None:
        plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="NO_ACTION",
            reason="POSITION_MISMATCH",
        )
        assert plan.requires_position_replay
        assert not plan.requires_ledger_replay
        assert not plan.requires_projection_rebuild

    def test_precheck_results(self) -> None:
        plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="NO_ACTION",
        )
        plan.precheck_results = {"facts_exist": True, "no_sequence_gap": True}
        assert plan.precheck_passed

    def test_precheck_failed(self) -> None:
        plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="NO_ACTION",
        )
        plan.precheck_results = {"facts_exist": False}
        assert not plan.precheck_passed

    def test_to_dict_roundtrip(self) -> None:
        plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="NO_ACTION",
            projection_action="REBUILD_REQUIRED",
            reason="test",
            execution_ids=["EXEC-001"],
            precheck_results={"ok": True},
        )
        data = plan.to_dict()
        restored = RecoveryPlan.from_dict(data)
        assert restored.source_execution_id == plan.source_execution_id
        assert restored.requires_position_replay
        assert not restored.requires_ledger_replay
        assert restored.requires_projection_rebuild


# ============================================================
# RecoveryJournal
# ============================================================

class TestRecoveryJournal:
    """Tests for RecoveryJournal audit trail."""

    def test_empty_journal(self) -> None:
        j = RecoveryJournal()
        assert j.last_state is None
        assert len(j.entries) == 0

    def test_append_entries(self) -> None:
        j = RecoveryJournal()
        j.append(RecoveryJournalEntryState.STARTED, "start")
        j.append(RecoveryJournalEntryState.PRECHECK_PASSED, "ok")
        j.append(RecoveryJournalEntryState.COMPLETED, "done")
        assert len(j.entries) == 3
        assert j.last_state == RecoveryJournalEntryState.COMPLETED

    def test_append_with_metadata(self) -> None:
        j = RecoveryJournal()
        j.append(RecoveryJournalEntryState.EVENTS_LOADED, "loaded 5 events", count=5)
        entry = j.entries[0]
        assert entry.metadata["count"] == 5

    def test_to_dict_roundtrip(self) -> None:
        j = RecoveryJournal()
        j.append(RecoveryJournalEntryState.STARTED, "begin")
        j.append(RecoveryJournalEntryState.COMPLETED, "end")
        data = j.to_dict()
        restored = RecoveryJournal.from_dict(data)
        assert len(restored.entries) == 2
        assert restored.last_state == RecoveryJournalEntryState.COMPLETED


# ============================================================
# RecoveryJob
# ============================================================

class TestRecoveryJob:
    """Tests for RecoveryJob core entity."""

    def _job(self, **kwargs) -> RecoveryJob:
        defaults = dict(
            job_id="REC-001",
            recovery_type=RecoveryType.POSITION_REPLAY,
            scope=RecoveryScope.for_execution("EXEC-001", "ACC-001", "NVDA"),
            source_check_id="CONSISTENCY-001",
        )
        defaults.update(kwargs)
        return RecoveryJob(**defaults)

    def test_creation_defaults(self) -> None:
        job = self._job()
        assert job.job_id == "REC-001"
        assert job.status == RecoveryStatus.CREATED
        assert job.attempt == 1
        assert job.max_attempts == 3
        assert not job.is_terminal
        assert job.is_active

    def test_recovery_key(self) -> None:
        job = self._job()
        assert job.recovery_key == "EXECUTION:ACC-001:NVDA:EXEC-001"

    def test_state_machine_success(self) -> None:
        job = self._job()
        job.mark_prechecking()
        assert job.status == RecoveryStatus.PRECHECKING
        assert job.started_at is not None

        job.mark_replaying()
        assert job.status == RecoveryStatus.REPLAYING

        job.mark_verifying()
        assert job.status == RecoveryStatus.VERIFYING

        job.mark_completed()
        assert job.status == RecoveryStatus.COMPLETED
        assert job.completed_at is not None
        assert job.is_terminal

    def test_state_machine_blocked(self) -> None:
        job = self._job()
        job.mark_prechecking()
        job.mark_blocked("Sequence gap detected")
        assert job.status == RecoveryStatus.BLOCKED
        assert job.failure_code == "BLOCKED"
        assert job.failure_reason == "Sequence gap detected"
        assert job.is_terminal

    def test_state_machine_failed(self) -> None:
        job = self._job()
        job.mark_prechecking()
        job.mark_replaying()
        job.mark_failed("REPLAY_ERROR", "Handler failed")
        assert job.status == RecoveryStatus.FAILED
        assert job.failure_code == "REPLAY_ERROR"
        # FAILED is NOT terminal — it can be retried
        assert not job.is_terminal

    def test_can_retry(self) -> None:
        job = self._job()
        job.mark_prechecking()
        job.mark_failed("ERR", "test")
        assert job.can_retry  # attempt 1 < 3

    def test_cannot_retry_after_max(self) -> None:
        job = self._job(attempt=3)
        job.mark_failed("ERR", "test")
        assert not job.can_retry

    def test_retry_transitions(self) -> None:
        job = self._job()
        job.mark_failed("ERR", "test")
        job.retry()
        assert job.attempt == 2
        assert job.status == RecoveryStatus.PRECHECKING
        assert job.failure_code is None

    def test_retry_exceeds_max_escalates(self) -> None:
        job = self._job(attempt=3)
        job.mark_failed("ERR", "test")
        job.retry()
        assert job.status == RecoveryStatus.ESCALATED
        assert job.failure_code == "ESCALATED"

    def test_mark_escalated(self) -> None:
        job = self._job()
        job.mark_escalated("Requires human intervention")
        assert job.status == RecoveryStatus.ESCALATED
        assert job.is_terminal

    def test_mark_deduplicated(self) -> None:
        job = self._job()
        job.mark_deduplicated()
        assert job.status == RecoveryStatus.DEDUPLICATED
        assert job.is_terminal

    def test_cannot_transition_from_terminal(self) -> None:
        job = self._job()
        job.mark_completed()
        import pytest
        with pytest.raises(ValueError):
            job.mark_prechecking()

    def test_journal_populated(self) -> None:
        job = self._job()
        job.mark_prechecking()
        job.mark_replaying()
        job.mark_completed()
        assert len(job.journal.entries) >= 3

    def test_to_dict_roundtrip(self) -> None:
        job = self._job()
        job.mark_prechecking()
        job.recovery_type = RecoveryType.FULL_TRANSACTION_REPLAY
        data = job.to_dict()
        restored = RecoveryJob.from_dict(data)
        assert restored.job_id == job.job_id
        assert restored.recovery_type == job.recovery_type
        assert restored.status == job.status
        assert restored.recovery_key == job.recovery_key

    def test_to_dict_roundtrip_with_plan(self) -> None:
        job = self._job()
        job.plan = RecoveryPlan(
            source_execution_id="EXEC-001",
            position_action="REPLAY_REQUIRED",
            ledger_action="NO_ACTION",
        )
        data = job.to_dict()
        restored = RecoveryJob.from_dict(data)
        assert restored.plan is not None
        assert restored.plan.requires_position_replay


# ============================================================
# RecoveryStatus
# ============================================================

class TestRecoveryStatus:
    """Tests for RecoveryStatus enum."""

    def test_terminal_states(self) -> None:
        assert RecoveryStatus.COMPLETED.is_terminal
        assert RecoveryStatus.BLOCKED.is_terminal
        assert RecoveryStatus.ESCALATED.is_terminal
        assert RecoveryStatus.DEDUPLICATED.is_terminal

    def test_active_states(self) -> None:
        assert RecoveryStatus.CREATED.is_active
        assert RecoveryStatus.PRECHECKING.is_active
        assert RecoveryStatus.REPLAYING.is_active
        assert RecoveryStatus.VERIFYING.is_active

    def test_non_active_states(self) -> None:
        assert not RecoveryStatus.COMPLETED.is_active
        assert not RecoveryStatus.FAILED.is_active
        assert not RecoveryStatus.BLOCKED.is_active

    def test_can_retry(self) -> None:
        assert RecoveryStatus.FAILED.can_retry
        assert not RecoveryStatus.COMPLETED.can_retry
        assert not RecoveryStatus.CREATED.can_retry


# ============================================================
# RecoveryType
# ============================================================

class TestRecoveryType:
    """Tests for RecoveryType enum."""

    def test_all_values(self) -> None:
        values = {e.value for e in RecoveryType}
        assert "POSITION_REPLAY" in values
        assert "LEDGER_REPLAY" in values
        assert "FULL_TRANSACTION_REPLAY" in values
        assert "PROJECTION_REBUILD" in values
