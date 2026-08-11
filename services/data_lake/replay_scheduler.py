"""
Replay Scheduler — schedules and manages multiple concurrent replay jobs
with resource allocation and priority queuing.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReplayJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReplayJob:
    job_id: str
    dataset: str
    start: datetime
    end: datetime
    speed: float = 1.0
    priority: int = 0
    status: ReplayJobStatus = ReplayJobStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    events_processed: int = 0
    total_events: int = 0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ReplayScheduler:
    """
    Schedules and manages multiple concurrent replay jobs.

    Features:
    - Priority-based job queuing
    - Concurrent replay execution
    - Resource-aware scheduling
    - Job status tracking
    - Cancellation support
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self.max_concurrent = max_concurrent
        self._jobs: dict[str, ReplayJob] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: dict[str, asyncio.Task] = {}
        self._scheduler_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info("Replay Scheduler started (max_concurrent=%d)", self.max_concurrent)

    async def stop(self) -> None:
        if self._scheduler_task:
            self._scheduler_task.cancel()
        for task in self._running.values():
            task.cancel()
        logger.info("Replay Scheduler stopped")

    async def submit(self, job: ReplayJob) -> str:
        """Submit a replay job to the queue."""
        self._jobs[job.job_id] = job
        # Higher priority = lower number in PriorityQueue
        await self._queue.put((-job.priority, job.job_id))
        logger.info("Replay job queued: %s (priority=%d)", job.job_id, job.priority)
        return job.job_id

    async def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = ReplayJobStatus.CANCELLED
        if job_id in self._running:
            self._running[job_id].cancel()
        logger.info("Replay job cancelled: %s", job_id)
        return True

    async def get_status(self, job_id: str) -> Optional[dict[str, Any]]:
        """Get status of a replay job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "dataset": job.dataset,
            "status": job.status.value,
            "progress": f"{job.events_processed}/{job.total_events}",
            "speed": job.speed,
            "created_at": job.created_at.isoformat(),
        }

    async def list_jobs(
        self, status: Optional[ReplayJobStatus] = None
    ) -> list[dict[str, Any]]:
        """List replay jobs, optionally filtered by status."""
        jobs = self._jobs.values()
        if status:
            jobs = [j for j in jobs if j.status == status]
        return [
            {
                "job_id": j.job_id,
                "dataset": j.dataset,
                "status": j.status.value,
                "priority": j.priority,
                "progress": f"{j.events_processed}/{j.total_events}",
            }
            for j in jobs
        ]

    async def _schedule_loop(self) -> None:
        """Main scheduling loop."""
        while True:
            await asyncio.sleep(0.5)

            # Clean completed tasks
            completed = [jid for jid, t in self._running.items() if t.done()]
            for jid in completed:
                del self._running[jid]

            # Start new jobs if capacity available
            while len(self._running) < self.max_concurrent and not self._queue.empty():
                _, job_id = await self._queue.get()
                job = self._jobs.get(job_id)
                if job and job.status == ReplayJobStatus.QUEUED:
                    job.status = ReplayJobStatus.RUNNING
                    job.started_at = datetime.now(timezone.utc)
                    task = asyncio.create_task(self._execute_job(job))
                    self._running[job_id] = task

    async def _execute_job(self, job: ReplayJob) -> None:
        """Execute a replay job (placeholder — delegates to ReplayEngine)."""
        try:
            logger.info("Executing replay job: %s", job.job_id)
            # In production, this would delegate to ReplayEngine.replay()
            await asyncio.sleep(0)  # Placeholder
            job.status = ReplayJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
        except asyncio.CancelledError:
            job.status = ReplayJobStatus.CANCELLED
        except Exception as e:
            job.status = ReplayJobStatus.FAILED
            job.error_message = str(e)
            logger.exception("Replay job failed: %s", job.job_id)
