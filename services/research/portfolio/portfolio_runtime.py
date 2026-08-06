"""Portfolio Runtime — job submission, state tracking, and execution control.

Bridges portfolio research with the Research Platform's runtime,
scheduler, and workflow engine for distributed portfolio operations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .portfolio_context import PortfolioContext

logger = logging.getLogger(__name__)


class PortfolioRuntimeState(str, Enum):
    """Portfolio runtime lifecycle states."""

    IDLE = "idle"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PortfolioJob:
    """Represents a single portfolio job in the runtime."""

    def __init__(
        self,
        job_id: Optional[str] = None,
        ctx: Optional[PortfolioContext] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.job_id = job_id or str(uuid4())
        self.ctx = ctx or PortfolioContext()
        self.config = config or {}
        self.state = PortfolioRuntimeState.IDLE
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: float = 0.0
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.cancel_event = asyncio.Event()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "state": self.state.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class PortfolioRuntime:
    """Job submission and execution control for portfolio research.

    Manages portfolio construction, optimization, and analysis jobs
    with progress tracking, cancellation, and result retrieval.
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._max_concurrent = max_concurrent
        self._jobs: Dict[str, PortfolioJob] = {}
        self._running: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._state = PortfolioRuntimeState.IDLE

    async def submit(
        self,
        ctx: PortfolioContext,
        config: Optional[Dict[str, Any]] = None,
        run_fn: Optional[Callable] = None,
    ) -> PortfolioJob:
        """Submit a portfolio job to the runtime."""
        job = PortfolioJob(ctx=ctx, config=config)
        self._jobs[job.job_id] = job
        job.state = PortfolioRuntimeState.QUEUED
        logger.info("Portfolio job queued: %s", job.job_id)

        if run_fn:
            asyncio.create_task(self._execute(job, run_fn))

        return job

    async def _execute(
        self, job: PortfolioJob, run_fn: Callable
    ) -> None:
        async with self._semaphore:
            if job.cancel_event.is_set():
                job.state = PortfolioRuntimeState.CANCELLED
                return

            job.state = PortfolioRuntimeState.RUNNING
            job.started_at = datetime.now(timezone.utc)
            self._running[job.job_id] = asyncio.current_task()  # type: ignore

            try:
                job.result = await run_fn(job.ctx, job.config, self._update_progress(job))
                job.state = PortfolioRuntimeState.COMPLETED
            except asyncio.CancelledError:
                job.state = PortfolioRuntimeState.CANCELLED
                job.error = "Job cancelled"
            except Exception as e:
                job.state = PortfolioRuntimeState.FAILED
                job.error = str(e)
                logger.exception("Portfolio job failed: %s", job.job_id)
            finally:
                job.completed_at = datetime.now(timezone.utc)
                self._running.pop(job.job_id, None)

    def _update_progress(self, job: PortfolioJob) -> Callable:
        def updater(pct: float) -> None:
            job.progress = max(0.0, min(1.0, pct))
        return updater

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.cancel_event.set()
        task = self._running.get(job_id)
        if task:
            task.cancel()
        return True

    def get_job(self, job_id: str) -> Optional[PortfolioJob]:
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        state: Optional[PortfolioRuntimeState] = None,
    ) -> List[PortfolioJob]:
        jobs = list(self._jobs.values())
        if state:
            jobs = [j for j in jobs if j.state == state]
        return jobs

    async def wait_for_job(
        self, job_id: str, timeout: Optional[float] = None
    ) -> PortfolioJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        start = datetime.now(timezone.utc)
        while job.state in (
            PortfolioRuntimeState.QUEUED,
            PortfolioRuntimeState.INITIALIZING,
            PortfolioRuntimeState.RUNNING,
        ):
            if timeout:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                if elapsed > timeout:
                    raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            await asyncio.sleep(0.1)

        return job

    @property
    def state(self) -> PortfolioRuntimeState:
        return self._state

    def status(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "total_jobs": len(self._jobs),
            "running_jobs": len(self._running),
            "jobs": {j: job.to_dict() for j, job in self._jobs.items()},
        }
