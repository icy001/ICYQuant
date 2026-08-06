"""Backtest Runtime — job submission, state tracking, and execution control.

Bridges backtesting with the Research Platform's runtime, scheduler,
and workflow engine for distributed backtest execution.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .backtest_context import BacktestContext

logger = logging.getLogger(__name__)


class BacktestRuntimeState(str, Enum):
    """Backtest runtime lifecycle states."""

    IDLE = "idle"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BacktestJob:
    """Represents a single backtest job in the runtime."""

    def __init__(
        self,
        job_id: Optional[str] = None,
        ctx: Optional[BacktestContext] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.job_id = job_id or str(uuid4())
        self.ctx = ctx or BacktestContext()
        self.config = config or {}
        self.state = BacktestRuntimeState.IDLE
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


class BacktestRuntime:
    """Orchestrates backtest execution with state tracking and cancellation.

    Responsibilities:
    * Submit backtest jobs for execution
    * Track progress and state transitions
    * Handle cancellation and error recovery
    * Bridge with distributed scheduler/workflow engine
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, BacktestJob] = {}
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
        self._max_concurrent: int = 4
        self._semaphore = asyncio.Semaphore(4)

    # ── job management ─────────────────────────────────────────────────────

    async def submit(
        self,
        ctx: BacktestContext,
        config: Optional[Dict[str, Any]] = None,
    ) -> BacktestJob:
        """Submit a new backtest job.

        Args:
            ctx: Backtest context with strategy and universe settings.
            config: Optional runtime configuration overrides.

        Returns:
            The created BacktestJob.
        """
        job = BacktestJob(ctx=ctx, config=config or {})
        job.state = BacktestRuntimeState.QUEUED
        self._jobs[job.job_id] = job
        logger.info("Backtest job submitted: %s", job.job_id[:8])
        return job

    async def execute(self, job: BacktestJob, executor: Callable) -> Dict[str, Any]:
        """Execute a submitted backtest job.

        Args:
            job: The BacktestJob to execute.
            executor: Async callable that takes (ctx, config) and returns result dict.

        Returns:
            Execution result dictionary.
        """
        if job.state != BacktestRuntimeState.QUEUED:
            raise RuntimeError(f"Cannot execute job in state: {job.state.value}")

        async with self._semaphore:
            job.state = BacktestRuntimeState.INITIALIZING
            job.started_at = datetime.now(timezone.utc)

            try:
                job.state = BacktestRuntimeState.RUNNING
                logger.info("Executing backtest job: %s", job.job_id[:8])

                # Execute the backtest
                result = await executor(job.ctx, job.config)

                job.state = BacktestRuntimeState.COMPLETED
                job.result = result
                job.progress = 1.0
                job.completed_at = datetime.now(timezone.utc)

                logger.info("Backtest job completed: %s", job.job_id[:8])
                if self._on_complete:
                    await self._on_complete(job)

                return result

            except asyncio.CancelledError:
                job.state = BacktestRuntimeState.CANCELLED
                job.error = "Cancelled by user"
                logger.warning("Backtest job cancelled: %s", job.job_id[:8])
                raise

            except Exception as exc:
                job.state = BacktestRuntimeState.FAILED
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                logger.exception("Backtest job failed: %s", job.job_id[:8])
                if self._on_error:
                    await self._on_error(job, exc)
                raise

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running backtest job.

        Args:
            job_id: The job identifier.

        Returns:
            True if the job was cancelled, False if not found/not cancellable.
        """
        job = self._jobs.get(job_id)
        if not job:
            logger.warning("Job not found: %s", job_id[:8])
            return False

        if job.state not in (
            BacktestRuntimeState.QUEUED,
            BacktestRuntimeState.RUNNING,
            BacktestRuntimeState.PAUSED,
        ):
            logger.warning("Cannot cancel job in state: %s", job.state.value)
            return False

        job.cancel_event.set()
        logger.info("Backtest job cancellation requested: %s", job_id[:8])
        return True

    async def pause(self, job_id: str) -> bool:
        """Pause a running backtest job."""
        job = self._jobs.get(job_id)
        if not job or job.state != BacktestRuntimeState.RUNNING:
            return False
        job.state = BacktestRuntimeState.PAUSED
        logger.info("Backtest job paused: %s", job_id[:8])
        return True

    async def resume(self, job_id: str) -> bool:
        """Resume a paused backtest job."""
        job = self._jobs.get(job_id)
        if not job or job.state != BacktestRuntimeState.PAUSED:
            return False
        job.state = BacktestRuntimeState.RUNNING
        logger.info("Backtest job resumed: %s", job_id[:8])
        return True

    # ── query ──────────────────────────────────────────────────────────────

    async def get_job(self, job_id: str) -> Optional[BacktestJob]:
        """Get a backtest job by ID."""
        return self._jobs.get(job_id)

    async def list_jobs(
        self,
        state: Optional[BacktestRuntimeState] = None,
        limit: int = 100,
    ) -> List[BacktestJob]:
        """List backtest jobs, optionally filtered by state."""
        jobs = list(self._jobs.values())
        if state:
            jobs = [j for j in jobs if j.state == state]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def get_stats(self) -> Dict[str, Any]:
        """Return runtime statistics."""
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "queued": sum(1 for j in jobs if j.state == BacktestRuntimeState.QUEUED),
            "running": sum(1 for j in jobs if j.state == BacktestRuntimeState.RUNNING),
            "completed": sum(1 for j in jobs if j.state == BacktestRuntimeState.COMPLETED),
            "failed": sum(1 for j in jobs if j.state == BacktestRuntimeState.FAILED),
            "cancelled": sum(1 for j in jobs if j.state == BacktestRuntimeState.CANCELLED),
            "max_concurrent": self._max_concurrent,
        }

    # ── callbacks ──────────────────────────────────────────────────────────

    def on_complete(self, callback: Callable) -> None:
        """Register callback for job completion."""
        self._on_complete = callback

    def on_error(self, callback: Callable) -> None:
        """Register callback for job errors."""
        self._on_error = callback

    def on_progress(self, callback: Callable) -> None:
        """Register callback for job progress updates."""
        self._on_progress = callback

    # ── cleanup ────────────────────────────────────────────────────────────

    async def cleanup(self, max_age_hours: float = 72.0) -> int:
        """Remove completed/failed jobs older than max_age_hours."""
        now = datetime.now(timezone.utc)
        removed = 0
        for job_id in list(self._jobs.keys()):
            job = self._jobs[job_id]
            if job.state in (
                BacktestRuntimeState.COMPLETED,
                BacktestRuntimeState.FAILED,
                BacktestRuntimeState.CANCELLED,
            ):
                age = (now - job.created_at).total_seconds() / 3600
                if age > max_age_hours:
                    del self._jobs[job_id]
                    removed += 1
        logger.info("Cleaned up %d old backtest jobs", removed)
        return removed
