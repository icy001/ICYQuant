"""ML Training Scheduler - Automated periodic training execution.

Schedules and manages training jobs with support for cron-based,
interval-based, and event-driven scheduling.

Usage::

    from infrastructure.ml.scheduler import MLScheduler

    scheduler = MLScheduler()
    scheduler.schedule(
        name="alpha_retrain",
        schedule="0 2 * * 0",  # Every Sunday at 2 AM
        task=lambda: train_model(),
    )
    scheduler.start()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from threading import Thread, Event


class ScheduleType(str, Enum):
    """Schedule type for training jobs."""

    CRON = "cron"
    INTERVAL = "interval"
    AT_TIME = "at_time"
    MANUAL = "manual"


class JobStatus(str, Enum):
    """Training job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """A scheduled ML training job.

    Attributes:
        id: Unique job ID.
        name: Human-readable job name.
        schedule_type: How the job is triggered.
        cron_expr: Cron expression (if cron type).
        interval_seconds: Interval in seconds (if interval type).
        at_hour: Hour of day (if at_time type).
        at_minute: Minute of hour (if at_time type).
        task: Callable to execute.
        status: Current job status.
        created_at: Creation timestamp.
        last_run: Last execution timestamp.
        next_run: Next scheduled timestamp.
        run_count: Total executions.
        fail_count: Total failures.
        max_retries: Max retries on failure.
        retry_delay: Seconds between retries.
        enabled: Whether the job is active.
    """

    id: str = ""
    name: str = ""
    schedule_type: ScheduleType = ScheduleType.MANUAL
    cron_expr: str = ""
    interval_seconds: int = 86400  # Default: 24 hours
    at_hour: int = 2
    at_minute: int = 0
    task: Optional[Callable[[], Any]] = None
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    fail_count: int = 0
    max_retries: int = 3
    retry_delay: int = 300  # 5 minutes
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "cron_expr": self.cron_expr,
            "interval_seconds": self.interval_seconds,
            "at_hour": self.at_hour,
            "at_minute": self.at_minute,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "fail_count": self.fail_count,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "enabled": self.enabled,
        }


class MLScheduler:
    """Scheduler for ML training jobs.

    Manages the lifecycle of automated training jobs with support
    for cron-based scheduling (mocked), interval-based, and
    at-time scheduling. Handles retries on failure.

    Usage::

        scheduler = MLScheduler()
        job = scheduler.schedule(
            name="Weekly Retrain",
            schedule_type=ScheduleType.AT_TIME,
            at_hour=2,
            at_minute=0,
            task=train_alpha_model,
        )
        scheduler.run_job(job.id)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        self._counter: int = 0
        self._running: bool = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None

    # ---- Schedule ----

    def schedule(
        self,
        name: str,
        schedule_type: ScheduleType = ScheduleType.MANUAL,
        task: Optional[Callable[[], Any]] = None,
        cron_expr: str = "",
        interval_seconds: int = 86400,
        at_hour: int = 2,
        at_minute: int = 0,
        max_retries: int = 3,
        retry_delay: int = 300,
        enabled: bool = True,
    ) -> ScheduledJob:
        """Schedule a new training job.

        Args:
            name: Human-readable job name.
            schedule_type: Trigger type.
            task: Callable to execute.
            cron_expr: Cron expression (for cron type).
            interval_seconds: Interval in seconds (for interval type).
            at_hour: Hour of day (for at_time type).
            at_minute: Minute of hour (for at_time type).
            max_retries: Max retries on failure.
            retry_delay: Delay between retries in seconds.
            enabled: Whether the job is active immediately.

        Returns:
            The ScheduledJob.
        """
        self._counter += 1
        job = ScheduledJob(
            id=f"job_{self._counter:04d}",
            name=name,
            schedule_type=schedule_type,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            at_hour=at_hour,
            at_minute=at_minute,
            task=task,
            max_retries=max_retries,
            retry_delay=retry_delay,
            enabled=enabled,
        )
        if schedule_type == ScheduleType.INTERVAL:
            job.next_run = time.time() + interval_seconds
        elif schedule_type == ScheduleType.AT_TIME:
            job.next_run = self._next_at_time(at_hour, at_minute)
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a scheduled job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[ScheduledJob]:
        """List all scheduled jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            return True
        return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.CANCELLED
            return True
        return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler."""
        return self._jobs.pop(job_id, None) is not None

    # ---- Execution ----

    def run_job(self, job_id: str) -> Optional[Any]:
        """Execute a scheduled job immediately (manual trigger).

        Handles retries on failure up to max_retries.
        Returns the task result or None if job not found.
        """
        job = self._jobs.get(job_id)
        if not job or not job.task:
            return None

        job.status = JobStatus.RUNNING
        job.last_run = time.time()
        job.run_count += 1

        for attempt in range(1, job.max_retries + 2):  # +1 for initial attempt, retries
            try:
                result = job.task()
                job.status = JobStatus.COMPLETED
                return result
            except Exception:
                if attempt <= job.max_retries:
                    time.sleep(min(job.retry_delay * attempt, 3600))
                else:
                    job.status = JobStatus.FAILED
                    job.fail_count += 1
                    return None
        return None

    def run_pending_jobs(self) -> List[Dict[str, Any]]:
        """Execute all jobs that are due to run.

        Returns list of results: {"job_id": ..., "success": bool}
        """
        results = []
        now = time.time()
        for job in list(self._jobs.values()):
            if not job.enabled or job.status == JobStatus.RUNNING:
                continue
            if job.next_run is not None and now >= job.next_run:
                self.run_job(job.id)
                results.append({"job_id": job.id, "success": job.status == JobStatus.COMPLETED})
                # Update next_run for interval jobs
                if job.schedule_type == ScheduleType.INTERVAL:
                    job.next_run = now + job.interval_seconds
                elif job.schedule_type == ScheduleType.AT_TIME:
                    job.next_run = self._next_at_time(job.at_hour, job.at_minute)
        return results

    # ---- Background Loop ----

    def start(self, check_interval: int = 60) -> None:
        """Start the scheduler background loop.

        Checks every `check_interval` seconds for due jobs.
        """
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, args=(check_interval,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler background loop."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    # ---- Stats ----

    def stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "active_jobs": sum(1 for j in jobs if j.enabled),
            "running": sum(1 for j in jobs if j.status == JobStatus.RUNNING),
            "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
            "total_runs": sum(j.run_count for j in jobs),
            "total_failures": sum(j.fail_count for j in jobs),
            "running_background": self._running,
        }

    # ---- Internal ----

    def _loop(self, check_interval: int) -> None:
        """Background loop that checks for due jobs."""
        while self._running and not self._stop_event.is_set():
            try:
                self.run_pending_jobs()
            except Exception:
                pass
            self._stop_event.wait(check_interval)

    @staticmethod
    def _next_at_time(hour: int, minute: int) -> float:
        """Calculate next occurrence of a specific time of day."""
        import datetime
        now = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return target.timestamp()
