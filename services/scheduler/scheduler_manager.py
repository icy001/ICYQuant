"""Scheduler Manager — coordinates all scheduler subsystems.

The :class:`SchedulerManager` is the central coordinator that manages:
* Scheduler Registry (schedule definitions)
* Scheduler Runtime (execution state)
* Scheduler Repository (persistence)
* Job lifecycles (create → queue → dispatch → complete)

All scheduling requests flow through this manager.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleStatus
from .models.job import JobDefinition, JobState, JobPriority
from .models.execution import ExecutionRecord, ExecutionState

logger = logging.getLogger(__name__)


class ManagerState:
    """Scheduler manager lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class SchedulerManager:
    """Central coordinator for all scheduler subsystems.

    The manager provides the integration layer that wires together
    registry, repository, and runtime. It handles job lifecycle
    management and provides a unified API for the engine.

    Usage::

        manager = SchedulerManager(registry, repository)
        await manager.start()
        job = manager.create_job(schedule, trigger_type="cron")
        await manager.dispatch_job(job)
    """

    def __init__(
        self,
        registry: Any = None,
        repository: Any = None,
        event_bus: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._state: str = ManagerState.STOPPED
        self._registry = registry
        self._repository = repository
        self._event_bus = event_bus

        # Job tracking
        self._jobs: Dict[str, JobDefinition] = {}
        self._executions: Dict[str, ExecutionRecord] = {}
        self._queue: List[JobDefinition] = []

        # Stats
        self._jobs_created: int = 0
        self._jobs_dispatched: int = 0
        self._jobs_completed: int = 0
        self._jobs_failed: int = 0
        self._started_at: Optional[datetime] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the scheduler manager."""
        with self._lock:
            if self._state == ManagerState.RUNNING:
                return
            self._state = ManagerState.STARTING

        logger.info("SchedulerManager: starting")
        self._started_at = datetime.now(timezone.utc)

        # Restore active jobs from repository
        if self._repository:
            try:
                active = await self._repository.list_active_jobs()
                for job in active:
                    self._jobs[job.job_id] = job
            except Exception:
                logger.exception("SchedulerManager: failed to restore active jobs")

        with self._lock:
            self._state = ManagerState.RUNNING

        logger.info("SchedulerManager: running (restored %d jobs)", len(self._jobs))

    async def stop(self) -> None:
        """Gracefully stop the manager."""
        with self._lock:
            if self._state in (ManagerState.STOPPED, ManagerState.STOPPING):
                return
            self._state = ManagerState.STOPPING

        logger.info("SchedulerManager: stopping")

        # Persist remaining active jobs
        if self._repository:
            for job in self._jobs.values():
                try:
                    await self._repository.save_job(job)
                except Exception:
                    logger.exception("SchedulerManager: failed to persist job %s", job.job_id)

        self._queue.clear()
        self._jobs.clear()
        self._executions.clear()

        with self._lock:
            self._state = ManagerState.STOPPED

        logger.info("SchedulerManager: stopped")

    # ── schedule management ────────────────────────────────────────────────

    def get_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Retrieve a schedule definition."""
        if self._registry:
            return self._registry.get(schedule_id)
        return None

    def list_schedules(
        self,
        status: Optional[ScheduleStatus] = None,
    ) -> List[ScheduleDefinition]:
        """List all registered schedules."""
        if self._registry:
            return self._registry.list_all(status=status)
        return []

    # ── job lifecycle ──────────────────────────────────────────────────────

    def create_job(
        self,
        schedule: ScheduleDefinition,
        trigger_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> JobDefinition:
        """Create a new job from a schedule trigger."""
        job = JobDefinition(
            job_id=f"job_{schedule.schedule_id}_{int(datetime.now(timezone.utc).timestamp())}",
            schedule_id=schedule.schedule_id,
            target=schedule.target,
            trigger_type=trigger_type,
            priority=priority,
            payload=payload or schedule.payload,
            state=JobState.CREATED,
            config=job_config_from_schedule(schedule),
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._jobs_created += 1
        logger.debug("SchedulerManager: created job %s for schedule %s", job.job_id, schedule.schedule_id)
        return job

    def enqueue_job(self, job: JobDefinition) -> JobDefinition:
        """Place a job in the dispatch queue."""
        queued = job.transition_to(JobState.QUEUED)
        with self._lock:
            self._jobs[queued.job_id] = queued
            self._queue.append(queued)
        return queued

    def dequeue_next(self) -> Optional[JobDefinition]:
        """Dequeue the highest-priority ready job."""
        with self._lock:
            if not self._queue:
                return None
            # Sort by priority (descending), then creation (ascending)
            self._queue.sort(key=lambda j: (-j.priority.value, j.created_at))
            return self._queue.pop(0)

    def dispatch_job(self, job: JobDefinition, worker_id: str) -> JobDefinition:
        """Mark a job as dispatched to a specific worker."""
        dispatched = job.transition_to(JobState.DISPATCHED).with_worker(worker_id)
        with self._lock:
            self._jobs[dispatched.job_id] = dispatched
            self._jobs_dispatched += 1
        return dispatched

    def complete_job(
        self, job: JobDefinition, result: ExecutionRecord,
    ) -> JobDefinition:
        """Mark a job as completed."""
        if result.result and result.result.value == "success":
            completed = job.transition_to(JobState.COMPLETED)
            self._jobs_completed += 1
        else:
            completed = job.transition_to(JobState.FAILED)
            self._jobs_failed += 1
        with self._lock:
            self._jobs[completed.job_id] = completed
            self._executions[result.execution_id] = result
        return completed

    def fail_job(self, job: JobDefinition, error: str) -> JobDefinition:
        """Mark a job as failed with an error message."""
        failed = JobDefinition(
            job_id=job.job_id,
            schedule_id=job.schedule_id,
            target=job.target,
            trigger_type=job.trigger_type,
            priority=job.priority,
            state=JobState.FAILED,
            payload=job.payload,
            config=job.config,
            assigned_worker=job.assigned_worker,
            error_message=error,
            updated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[failed.job_id] = failed
            self._jobs_failed += 1
        return failed

    # ── query ──────────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[JobDefinition]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    def list_active_jobs(self) -> List[JobDefinition]:
        """List all currently active/running jobs."""
        with self._lock:
            return [
                j for j in self._jobs.values()
                if j.state in (
                    JobState.CREATED, JobState.QUEUED, JobState.SCHEDULED,
                    JobState.DISPATCHED, JobState.RUNNING,
                )
            ]

    def get_queue(self) -> List[JobDefinition]:
        """Return the current queue snapshot."""
        with self._lock:
            return list(self._queue)

    def queue_length(self) -> int:
        """Return the current queue length."""
        return len(self._queue)

    # ── observability ──────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == ManagerState.RUNNING

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report."""
        return {
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "jobs_created": self._jobs_created,
            "jobs_dispatched": self._jobs_dispatched,
            "jobs_completed": self._jobs_completed,
            "jobs_failed": self._jobs_failed,
            "active_jobs": len([j for j in self._jobs.values() if j.state not in (
                JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED,
            )]),
            "queue_length": self.queue_length(),
        }


def job_config_from_schedule(schedule: ScheduleDefinition) -> Dict[str, Any]:
    """Extract job-relevant config from a schedule definition."""
    return {
        "timeout_seconds": schedule.config.timeout_seconds,
        "retry_max": schedule.config.retry_max,
        "retry_delay_seconds": schedule.config.retry_delay_seconds,
        "resource_requirements": {},
        "worker_affinity": None,
        "broadcast": False,
        "singleton": False,
    }
