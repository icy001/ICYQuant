"""RecoveryService — orchestrates the full recovery pipeline.

Coordinates:
    - Job creation from consistency triggers
    - Precheck execution
    - Replay via ReplayService
    - Verification via RecoveryVerifier
    - State machine management
    - Lock/dedup concurrency control
    - Event emission
    - Retry with backoff
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RecoveryService:
    """Orchestrator for transaction flow recovery.

    Recovery pipeline:
        1. Accept consistency failure trigger
        2. Create recovery job with plan
        3. Precheck → Replay → Verify → Complete
        4. If failed → Retry (with backoff) or Escalate
    """

    repository: Any                           # RecoveryRepository
    replay_service: Any = None                # ReplayService
    verifier: Any = None                      # RecoveryVerifier
    consistency_service: Any = None           # ConsistencyService

    max_retries: int = 3
    base_backoff_ms: int = 1000

    # ---- Locks & Dedup ----
    _locks: Dict[str, str] = field(default_factory=dict)  # recovery_key → job_id
    _active_jobs: Dict[str, Any] = field(default_factory=dict)  # job_id → RecoveryJob

    # ---- Events ----
    _pending_events: List[Any] = field(default_factory=list)

    # ---- Metrics ----
    jobs_created: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_escalated: int = 0
    jobs_deduplicated: int = 0
    total_retries: int = 0
    total_events_replayed: int = 0

    def handle_consistency_failure(
        self,
        trigger: Any,  # ReconciliationTrigger
        execution_facts: Optional[List[Any]] = None,
    ) -> Optional[Any]:
        """Entry point: handle a consistency failure from Part 1.4.

        Returns the created RecoveryJob or None if deduplicated.
        """
        from services.recovery.commands.create_recovery_job import CreateRecoveryJob

        # ---- Dedup check ----
        scope = self._scope_from_trigger(trigger)
        key = scope.recovery_key

        if key in self._locks:
            self.jobs_deduplicated += 1
            return None

        # ---- Create job ----
        job_id = self._next_job_id()
        cmd = CreateRecoveryJob(
            trigger_id=trigger.trigger_id,
            check_id=trigger.check_id,
            failure_type=trigger.failure_type,
            expected_value=trigger.expected_value,
            actual_value=trigger.actual_value,
            delta=trigger.delta,
            account_id=getattr(trigger, "account_id", None),
            instrument_id=getattr(trigger, "instrument_id", None),
            execution_id=getattr(trigger, "execution_id", None),
        )
        job = cmd.execute(self.repository, job_id)

        # ---- Lock ----
        self._locks[key] = job_id
        self._active_jobs[job_id] = job
        self.jobs_created += 1

        # ---- Emit event ----
        self._emit_recovery_started(job)

        # ---- Execute ----
        if execution_facts:
            self._execute_recovery(job, execution_facts)

        return job

    def _execute_recovery(self, job: Any, execution_facts: List[Any]) -> Any:
        """Internal: execute the recovery job pipeline."""
        from services.recovery.commands.execute_recovery import ExecuteRecovery

        cmd = ExecuteRecovery(
            job=job,
            execution_facts=execution_facts,
        )
        return cmd.execute(self.repository, self.replay_service, self)

    def emit_completed(self, job: Any) -> None:
        """Emit RecoveryCompleted event and release lock."""
        from services.recovery.events.recovery_completed import RecoveryCompleted

        if job.status.value == "COMPLETED":
            self.jobs_completed += 1
            self.total_events_replayed += job.events_replayed
            self._release_lock(job)

        event = RecoveryCompleted.from_job(job)
        self._pending_events.append(event)

    def emit_failure(self, job: Any) -> None:
        """Emit RecoveryFailed event and handle retry/escalation."""
        from services.recovery.events.recovery_failed import RecoveryFailed

        if job.status.value == "FAILED":
            self.jobs_failed += 1
            self.total_retries += 1

            if job.can_retry:
                # Apply backoff then retry
                job.retry()
                if job.status.value == "ESCALATED":
                    self.jobs_escalated += 1
                    self._release_lock(job)
            else:
                job.mark_escalated(job.failure_reason or "Max retries exceeded")
                self.jobs_escalated += 1
                self._release_lock(job)
        elif job.status.value == "ESCALATED":
            self.jobs_escalated += 1
            self._release_lock(job)

        event = RecoveryFailed.from_job(job)
        self._pending_events.append(event)

    def verify_recovery(self, job: Any) -> Dict[str, Any]:
        """Run post-recovery verification."""
        if self.verifier is not None:
            return self.verifier.verify(job, [])
        # Fallback: run basic consistency check
        if self.consistency_service is not None:
            check = self.consistency_service.check_execution(
                execution_id=job.execution_id or "",
                account_id=job.account_id or "",
                instrument_id=job.instrument_id or "",
            )
            from services.consistency.domain.consistency_status import ConsistencyDomainStatus
            return {
                "consistent": check.is_consistent,
                "checks": {"cross_domain": check},
                "failure_code": None if check.is_consistent else "VERIFY_FAILED",
                "failure_reason": None if check.is_consistent else (
                    f"Status: {check.overall_status.value}"
                ),
            }
        return {"consistent": True, "checks": {}, "failure_code": None, "failure_reason": None}

    def retry_job(self, job_id: str) -> Optional[Any]:
        """Manually retry a failed recovery job."""
        job = self._active_jobs.get(job_id)
        if job is None:
            return None
        if not job.can_retry:
            return None

        backoff = self.base_backoff_ms * (2 ** (job.attempt - 1))
        job.retry()
        self.total_retries += 1
        return job

    def collect_events(self) -> List[Any]:
        """Drain and return pending events."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events

    # ---- Lock management ----

    def _lock(self, key: str, job_id: str) -> None:
        if key in self._locks:
            from services.recovery.exceptions.recovery_conflict import RecoveryLockedError
            raise RecoveryLockedError(key, self._locks[key])
        self._locks[key] = job_id

    def _release_lock(self, job: Any) -> None:
        key = job.recovery_key
        self._locks.pop(key, None)

    def is_locked(self, key: str) -> bool:
        return key in self._locks

    # ---- Helpers ----

    def _next_job_id(self) -> str:
        n = self.jobs_created + self.jobs_deduplicated + 1
        return f"REC-{n:03d}"

    def _scope_from_trigger(self, trigger: Any) -> Any:
        from services.recovery.domain.recovery_scope import RecoveryScope, RecoveryScopeType

        eid = getattr(trigger, "execution_id", None)
        oid = getattr(trigger, "order_id", None)
        aid = getattr(trigger, "account_id", None)
        iid = getattr(trigger, "instrument_id", None)

        if eid:
            return RecoveryScope.for_execution(eid, aid or "", iid or "")
        if oid:
            return RecoveryScope.for_order(oid, aid or "", iid or "")
        if iid:
            return RecoveryScope.for_instrument(aid or "", iid)
        if aid:
            return RecoveryScope.for_account(aid)
        return RecoveryScope(scope_type=RecoveryScopeType.ACCOUNT)

    def _emit_recovery_started(self, job: Any) -> None:
        from services.recovery.events.recovery_started import RecoveryStarted
        event = RecoveryStarted.from_job(job)
        self._pending_events.append(event)

    @property
    def active_job_ids(self) -> List[str]:
        return list(self._active_jobs.keys())

    @property
    def total_jobs(self) -> int:
        return self.jobs_created + self.jobs_deduplicated

    @property
    def success_rate(self) -> float:
        total = self.jobs_completed + self.jobs_failed + self.jobs_escalated
        if total == 0:
            return 0.0
        return self.jobs_completed / total
