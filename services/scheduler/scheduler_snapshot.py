"""Scheduler Snapshot — captures scheduler state for recovery, debugging, and replay.

The :class:`SchedulerSnapshot` captures the complete scheduler runtime
state including active jobs, queue contents, timers, and scheduler state.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.job import JobDefinition

logger = logging.getLogger(__name__)


class SchedulerSnapshot:
    """Immutable snapshot of scheduler runtime state.

    Captures the complete state at a point in time for:
    * Recovery after restart or failure
    * Debugging scheduler behavior
    * Replay and regression testing

    Usage::

        snapshot = SchedulerSnapshot.capture(jobs, queue, state, config)
        restored = SchedulerSnapshot.restore(snapshot_data)
    """

    def __init__(
        self,
        snapshot_id: Optional[str] = None,
        captured_at: Optional[datetime] = None,
    ) -> None:
        self.snapshot_id = snapshot_id or str(uuid.uuid4())
        self.captured_at = captured_at or datetime.now(timezone.utc)

        # State
        self.scheduler_state: str = ""
        self.runtime_phase: str = ""

        # Data
        self.active_jobs: List[Dict[str, Any]] = []
        self.job_queue: List[Dict[str, Any]] = []
        self.executions: List[Dict[str, Any]] = []
        self.contexts: List[Dict[str, Any]] = []
        self.timer_states: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    @classmethod
    def capture(
        cls,
        jobs: List[JobDefinition],
        queue: List[JobDefinition],
        state: str = "",
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SchedulerSnapshot:
        """Capture the current scheduler state.

        Args:
            jobs: Active jobs.
            queue: Pending jobs in the dispatch queue.
            state: Scheduler engine state.
            config: Current configuration.
            metadata: Additional metadata.

        Returns:
            A new :class:`SchedulerSnapshot` with captured state.
        """
        snapshot = cls()
        snapshot.scheduler_state = state
        snapshot.active_jobs = [job.to_dict() for job in jobs]
        snapshot.job_queue = [job.to_dict() for job in queue]
        snapshot.config = config or {}
        snapshot.metadata = {
            "capture_reason": "manual",
            "total_jobs": len(jobs),
            "queue_depth": len(queue),
            **(metadata or {}),
        }
        return snapshot

    @classmethod
    def capture_from_runtime(
        cls,
        runtime: Any,  # SchedulerRuntime
        config: Optional[Dict[str, Any]] = None,
    ) -> SchedulerSnapshot:
        """Capture state from a live scheduler runtime."""
        snapshot = cls()

        try:
            jobs = runtime.list_jobs()
            snapshot.active_jobs = [j.to_dict() for j in jobs]
            snapshot.scheduler_state = "running" if runtime.is_running else "stopped"
            snapshot.config = config or {}
            snapshot.metadata = {
                "capture_reason": "runtime_capture",
                "total_jobs": len(jobs),
            }
        except Exception as exc:
            logger.warning("SchedulerSnapshot: capture from runtime failed: %s", exc)

        return snapshot

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary for storage."""
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at.isoformat(),
            "scheduler_state": self.scheduler_state,
            "runtime_phase": self.runtime_phase,
            "active_jobs": self.active_jobs,
            "job_queue": self.job_queue,
            "executions": self.executions,
            "contexts": self.contexts,
            "timer_states": self.timer_states,
            "config": self.config,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SchedulerSnapshot:
        """Restore a snapshot from serialized data."""
        snapshot = cls(
            snapshot_id=data.get("snapshot_id"),
            captured_at=(
                datetime.fromisoformat(data["captured_at"])
                if data.get("captured_at") else None
            ),
        )
        snapshot.scheduler_state = data.get("scheduler_state", "")
        snapshot.runtime_phase = data.get("runtime_phase", "")
        snapshot.active_jobs = data.get("active_jobs", [])
        snapshot.job_queue = data.get("job_queue", [])
        snapshot.executions = data.get("executions", [])
        snapshot.contexts = data.get("contexts", [])
        snapshot.timer_states = data.get("timer_states", {})
        snapshot.config = data.get("config", {})
        snapshot.metadata = data.get("metadata", {})
        return snapshot

    def restore_jobs(self) -> List[Dict[str, Any]]:
        """Restore active jobs from the snapshot."""
        return list(self.active_jobs)

    def restore_queue(self) -> List[Dict[str, Any]]:
        """Restore the job queue from the snapshot."""
        return list(self.job_queue)

    def __repr__(self) -> str:
        return (
            f"SchedulerSnapshot(id={self.snapshot_id[:8]}, "
            f"jobs={len(self.active_jobs)}, queue={len(self.job_queue)})"
        )
