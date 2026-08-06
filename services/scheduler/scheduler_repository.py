"""Scheduler Repository — persistence layer for schedules, jobs, and executions.

The :class:`SchedulerRepository` provides durable storage for all
scheduler state with support for PostgreSQL, object storage, and
cluster sync (reserved for future use).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition
from .models.job import JobDefinition
from .models.execution import ExecutionRecord

logger = logging.getLogger(__name__)


class SchedulerRepository:
    """Durable persistence layer for scheduler state.

    In-memory implementation for the foundation layer. Supports
    CRUD operations for schedules, jobs, and execution records.
    Designed to be swapped with PostgreSQL / object storage backends.

    Usage::

        repo = SchedulerRepository()
        await repo.initialize()
        await repo.save_schedule(schedule)
        history = await repo.get_history()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Storage
        self._schedules: Dict[str, ScheduleDefinition] = {}
        self._jobs: Dict[str, JobDefinition] = {}
        self._executions: Dict[str, ExecutionRecord] = {}
        self._snapshots: Dict[str, List[Dict[str, Any]]] = {}

        # State
        self._initialized: bool = False
        self._created_at: Optional[datetime] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the repository."""
        with self._lock:
            self._initialized = True
            self._created_at = datetime.now(timezone.utc)
        logger.info("SchedulerRepository: initialized")

    async def shutdown(self) -> None:
        """Shut down the repository."""
        with self._lock:
            self._initialized = False
        logger.info("SchedulerRepository: shut down")

    # ── schedule persistence ───────────────────────────────────────────────

    async def save_schedule(self, schedule: ScheduleDefinition) -> None:
        """Persist a schedule definition."""
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        logger.debug("SchedulerRepository: saved schedule %s", schedule.schedule_id)

    async def load_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Load a schedule definition by ID."""
        with self._lock:
            return self._schedules.get(schedule_id)

    async def load_all_schedules(self) -> List[ScheduleDefinition]:
        """Load all persisted schedules."""
        with self._lock:
            return list(self._schedules.values())

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a schedule definition."""
        with self._lock:
            self._schedules.pop(schedule_id, None)
        logger.debug("SchedulerRepository: deleted schedule %s", schedule_id)

    # ── job persistence ────────────────────────────────────────────────────

    async def save_job(self, job: JobDefinition) -> None:
        """Persist a job definition."""
        with self._lock:
            self._jobs[job.job_id] = job
        logger.debug("SchedulerRepository: saved job %s", job.job_id)

    async def load_job(self, job_id: str) -> Optional[JobDefinition]:
        """Load a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    async def list_active_jobs(self) -> List[JobDefinition]:
        """List all active (non-terminal) jobs."""
        from .models.job import JobState
        with self._lock:
            return [
                j for j in self._jobs.values()
                if j.state not in (
                    JobState.COMPLETED, JobState.FAILED,
                    JobState.CANCELLED, JobState.TIMEOUT,
                )
            ]

    async def load_jobs_by_schedule(self, schedule_id: str) -> List[JobDefinition]:
        """Load all jobs associated with a schedule."""
        with self._lock:
            return [j for j in self._jobs.values() if j.schedule_id == schedule_id]

    # ── execution persistence ──────────────────────────────────────────────

    async def save_execution(self, execution: ExecutionRecord) -> None:
        """Persist an execution record."""
        with self._lock:
            self._executions[execution.execution_id] = execution
        logger.debug("SchedulerRepository: saved execution %s", execution.execution_id)

    async def load_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Load an execution record by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    async def get_history(
        self, schedule_id: Optional[str] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve execution history, optionally filtered by schedule."""
        with self._lock:
            executions = list(self._executions.values())
            if schedule_id:
                executions = [e for e in executions if e.schedule_id == schedule_id]
            # Sort by created_at descending
            executions.sort(key=lambda e: e.created_at, reverse=True)
            return [e.to_dict() for e in executions[:limit]]

    # ── snapshot persistence ───────────────────────────────────────────────

    async def save_snapshot(self, key: str, data: Dict[str, Any]) -> None:
        """Save a scheduler snapshot."""
        with self._lock:
            self._snapshots.setdefault(key, []).append(data)
        logger.debug("SchedulerRepository: saved snapshot %s", key)

    async def load_snapshot(self, key: str) -> Optional[Dict[str, Any]]:
        """Load the latest snapshot for a key."""
        with self._lock:
            history = self._snapshots.get(key, [])
            return history[-1] if history else None

    async def list_snapshots(self, key: str) -> List[Dict[str, Any]]:
        """List all snapshots for a key."""
        with self._lock:
            return list(self._snapshots.get(key, []))

    # ── observability ──────────────────────────────────────────────────────

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report."""
        return {
            "initialized": self._initialized,
            "created_at": self._created_at.isoformat() if self._created_at else None,
            "schedules_count": len(self._schedules),
            "jobs_count": len(self._jobs),
            "executions_count": len(self._executions),
            "snapshot_keys": list(self._snapshots.keys()),
        }
