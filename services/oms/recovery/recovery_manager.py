"""RecoveryManager — coordinates recovery operations.

The RecoveryManager handles UNKNOWN states by:
  1. Creating a RecoveryJob
  2. Querying the Execution layer
  3. Reconciling the result
  4. Determining repair action
  5. Returning the action for the caller to execute

CRITICAL: Recovery never invents execution facts. If the execution
layer returns UNKNOWN, the order stays UNKNOWN.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .recovery_state import RecoveryState
from .recovery_result import RecoveryJob
from .recovery_policy import RecoveryPolicy


class RecoveryManager:
    """Manages recovery for orders in unknown states.

    The manager is idempotent — duplicate recovery requests for
    the same order return the existing job.
    """

    def __init__(self, policy: Optional[RecoveryPolicy] = None) -> None:
        self._policy = policy or RecoveryPolicy.default()
        self._jobs: Dict[str, RecoveryJob] = {}  # order_id → job

    def create_job(self, order_id: str,
                   trigger: str = "MANUAL") -> RecoveryJob:
        """Create a recovery job for an order.

        If a job already exists and is not terminal, returns it.
        If a job exists and is terminal, creates a new one.
        """
        existing = self._jobs.get(order_id)
        if existing and not existing.is_terminal:
            return existing

        job = RecoveryJob(
            order_id=order_id,
            trigger=trigger,
            max_attempts=self._policy.max_attempts,
        )
        self._jobs[order_id] = job
        return job

    def execute_recovery(self, order_id: str,
                         query_fn) -> RecoveryJob:
        """Execute a recovery by querying the execution layer.

        Args:
            order_id: The order to recover.
            query_fn: A function that takes order_id and returns
                      a dict with 'status' and optionally 'report'.

        Returns:
            The updated RecoveryJob.
        """
        job = self.create_job(order_id)
        if job.is_terminal:
            return job

        if not self._policy.auto_recovery_enabled:
            job.mark_escalated("Auto-recovery disabled")
            return job

        job.start()

        while job.can_retry:
            job.record_attempt()
            try:
                result = query_fn(order_id)
                if result.get("status") and result["status"] != "UNKNOWN":
                    job.mark_recovered(result)
                    return job
            except Exception as e:
                job.error = str(e)

        # All attempts exhausted
        if self._policy.escalate_on_failure:
            job.mark_escalated("Recovery failed after max attempts")
        else:
            job.mark_failed("Recovery failed after max attempts")

        return job

    def get_job(self, order_id: str) -> Optional[RecoveryJob]:
        return self._jobs.get(order_id)

    def get_all_jobs(self) -> List[RecoveryJob]:
        return list(self._jobs.values())

    def get_active_jobs(self) -> List[RecoveryJob]:
        return [j for j in self._jobs.values() if not j.is_terminal]

    @property
    def policy(self) -> RecoveryPolicy:
        return self._policy
