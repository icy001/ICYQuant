"""ExecuteRecovery — orchestrate the replay of events for a recovery job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ExecuteRecovery:
    """Command: execute a recovery job by replaying immutable execution facts.

    This is the core of the recovery pipeline — it replays events to regenerate
    Position and/or Ledger state, then triggers verification.
    """

    job: Any  # RecoveryJob
    execution_facts: List[Any] = None  # type: ignore[assignment]
    position_handler: Optional[Any] = None
    ledger_handler: Optional[Any] = None

    def __post_init__(self):
        if self.execution_facts is None:
            self.execution_facts = []

    def execute(
        self,
        repository: Any,
        replay_service: Any,
        recovery_service: Any,
    ) -> Any:
        """Execute the recovery flow: precheck → replay → verify."""
        from services.recovery.domain.recovery_job import RecoveryJournalEntryState
        from services.recovery.domain.recovery_status import RecoveryStatus, RecoveryType

        job = self.job

        # Phase 1: Precheck
        job.mark_prechecking()
        repository.save(job)

        precheck_result = self._run_precheck(job)
        if not precheck_result["passed"]:
            if precheck_result.get("block"):
                job.mark_blocked(precheck_result["reason"])
            else:
                job.mark_failed("PRECHECK_FAILED", precheck_result["reason"])
            repository.save(job)
            recovery_service.emit_failure(job)
            return job

        job.journal.append(
            RecoveryJournalEntryState.PRECHECK_PASSED,
            "All preconditions met",
            results=precheck_result,
        )
        repository.save(job)

        # Phase 2: Replay
        job.mark_replaying()
        repository.save(job)

        start = datetime.now(timezone.utc)
        replay_result = replay_service.replay(job, self.execution_facts)
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        job.events_replayed = replay_result.get("events_replayed", 0)
        job.events_loaded = replay_result.get("events_loaded", len(self.execution_facts))
        job.replay_duration_ms = elapsed

        if not replay_result.get("success", False):
            job.mark_failed(
                replay_result.get("error_code", "REPLAY_FAILED"),
                replay_result.get("error_reason", "Replay failed"),
            )
            repository.save(job)
            recovery_service.emit_failure(job)
            return job

        if job.recovery_type == RecoveryType.POSITION_REPLAY:
            job.journal.append(RecoveryJournalEntryState.POSITION_REPLAYED, "Position events replayed")
        elif job.recovery_type == RecoveryType.LEDGER_REPLAY:
            job.journal.append(RecoveryJournalEntryState.LEDGER_REPLAYED, "Ledger events replayed")
        elif job.recovery_type == RecoveryType.FULL_TRANSACTION_REPLAY:
            job.journal.append(RecoveryJournalEntryState.POSITION_REPLAYED, "Position events replayed")
            job.journal.append(RecoveryJournalEntryState.LEDGER_REPLAYED, "Ledger events replayed")
        job.journal.append(
            RecoveryJournalEntryState.PROJECTION_REBUILT,
            f"Replayed {job.events_replayed} events in {elapsed}ms",
        )
        repository.save(job)

        # Phase 3: Verify
        job.mark_verifying()
        repository.save(job)

        verify_result = recovery_service.verify_recovery(job)
        if verify_result.get("consistent", False):
            job.mark_completed()
            job.journal.append(RecoveryJournalEntryState.CONSISTENCY_VERIFIED, "All domains consistent")
            repository.save(job)
            recovery_service.emit_completed(job)
        else:
            job.mark_failed(
                verify_result.get("failure_code", "VERIFY_FAILED"),
                verify_result.get("failure_reason", "Post-recovery consistency check failed"),
            )
            repository.save(job)
            recovery_service.emit_failure(job)

            # Retry if possible
            if job.can_retry:
                job.retry()
                repository.save(job)

        return job

    def _run_precheck(self, job: Any) -> Dict[str, Any]:
        """Run pre-execution safety checks."""
        checks: Dict[str, bool] = {}
        reasons: List[str] = []

        # 1. Execution facts exist
        if not self.execution_facts:
            checks["facts_exist"] = False
            reasons.append("No execution facts provided for replay")
        else:
            checks["facts_exist"] = True

        # 2. No sequence gaps
        seq_check = self._check_sequence()
        checks["no_sequence_gap"] = seq_check["ok"]
        if not seq_check["ok"]:
            reasons.append(seq_check["reason"])

        # 3. Facts are confirmed (all have occurred_at)
        all_confirmed = all(
            getattr(f, "occurred_at", None) is not None for f in self.execution_facts
        )
        checks["all_confirmed"] = all_confirmed
        if not all_confirmed:
            reasons.append("Some execution facts are not yet confirmed")

        # 4. No duplicate active recovery
        checks["no_conflict"] = True  # repository layer handles this

        # Update plan with precheck results
        if job.plan is not None:
            job.plan.precheck_results = checks

        passed = all(checks.values())
        return {
            "passed": passed,
            "block": not seq_check["ok"],
            "reason": "; ".join(reasons) if reasons else "All checks passed",
            "checks": checks,
        }

    def _check_sequence(self) -> Dict[str, Any]:
        """Validate event sequence is contiguous."""
        seqs = []
        for f in self.execution_facts:
            seq = getattr(f, "sequence_number", None)
            if seq is not None:
                seqs.append(seq)

        if len(seqs) < 2:
            return {"ok": True, "reason": ""}

        sorted_seqs = sorted(seqs)
        for i in range(1, len(sorted_seqs)):
            if sorted_seqs[i] != sorted_seqs[i - 1] + 1:
                return {
                    "ok": False,
                    "reason": f"Sequence gap: expected {sorted_seqs[i-1] + 1}, got {sorted_seqs[i]}",
                }
        return {"ok": True, "reason": ""}


def execute_recovery(
    job: Any,
    repository: Any,
    replay_service: Any,
    recovery_service: Any,
    execution_facts: Optional[List[Any]] = None,
) -> Any:
    """Convenience function to execute a recovery job."""
    cmd = ExecuteRecovery(
        job=job,
        execution_facts=execution_facts or [],
    )
    return cmd.execute(repository, replay_service, recovery_service)
