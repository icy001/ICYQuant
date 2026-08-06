"""Runtime Scheduler — the internal event loop that drives trigger→queue→dispatch→worker→workflow.

The :class:`RuntimeScheduler` is the heartbeat of the distributed scheduler
runtime. It continuously evaluates triggers, enqueues ready jobs, dispatches
to workers, and coordinates with the workflow engine.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .runtime_state import RuntimePhase
from ..models.job import JobDefinition, JobState
from ..models.execution import ExecutionRecord

logger = logging.getLogger(__name__)


class RuntimeScheduler:
    """Internal runtime event loop for trigger evaluation and job dispatch.

    Provides the core scheduling loop that:
    1. Evaluates active triggers
    2. Enqueues ready jobs into a priority queue
    3. Dispatches jobs to available workers
    4. Coordinates execution with the Workflow Engine

    Usage::

        rs = RuntimeScheduler()
        rs.on_trigger(lambda: get_due_triggers())
        rs.on_dispatch(lambda job: send_to_worker(job))
        await rs.start()
    """

    def __init__(self, tick_interval: float = 0.1, max_queue_size: int = 10000) -> None:
        self._lock = threading.RLock()
        self._tick_interval = tick_interval
        self._max_queue_size = max_queue_size

        self._running: bool = False
        self._paused: bool = False

        # Priority queue: list of (priority, timestamp, job)
        self._queue: List[Any] = []
        self._active_jobs: Dict[str, JobDefinition] = {}
        self._completed_jobs: Dict[str, JobDefinition] = {}

        # Hooks
        self._on_trigger: Optional[Callable[[], List[Any]]] = None
        self._on_dispatch: Optional[Callable[[JobDefinition], Any]] = None
        self._on_complete: Optional[Callable[[JobDefinition, ExecutionRecord], None]] = None

        # Stats
        self._jobs_processed: int = 0
        self._jobs_dispatched: int = 0
        self._dispatch_errors: int = 0
        self._loop_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the runtime scheduler loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = False
            self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("RuntimeScheduler: started (tick=%ss)", self._tick_interval)

    async def stop(self) -> None:
        """Stop the runtime scheduler loop gracefully."""
        with self._lock:
            self._running = False

        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        logger.info("RuntimeScheduler: stopped")

    def pause(self) -> None:
        """Pause scheduling (running jobs continue)."""
        with self._lock:
            self._paused = True
        logger.info("RuntimeScheduler: paused")

    def resume(self) -> None:
        """Resume scheduling."""
        with self._lock:
            self._paused = False
        logger.info("RuntimeScheduler: resumed")

    # ── hooks ──────────────────────────────────────────────────────────────

    def on_trigger(self, callback: Callable[[], List[Any]]) -> None:
        """Register the trigger evaluation callback."""
        self._on_trigger = callback

    def on_dispatch(self, callback: Callable[[JobDefinition], Any]) -> None:
        """Register the dispatch callback."""
        self._on_dispatch = callback

    def on_complete(self, callback: Callable[[JobDefinition, ExecutionRecord], None]) -> None:
        """Register the completion callback."""
        self._on_complete = callback

    # ── job management ─────────────────────────────────────────────────────

    def enqueue(self, job: JobDefinition) -> bool:
        """Place a job into the priority queue."""
        with self._lock:
            if len(self._queue) >= self._max_queue_size:
                logger.warning("RuntimeScheduler: queue full, dropping job %s", job.job_id)
                return False
            # Higher priority first, then earlier timestamp
            entry = (-job.priority.value, job.created_at, job)
            self._queue.append(entry)
            self._queue.sort(key=lambda x: (x[0], x[1]))
            self._active_jobs[job.job_id] = job
        return True

    def complete_job(self, job: JobDefinition) -> None:
        """Move a job from active to completed."""
        with self._lock:
            self._active_jobs.pop(job.job_id, None)
            self._completed_jobs[job.job_id] = job
            self._jobs_processed += 1

    # ── internal loop ──────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Main scheduler tick loop."""
        while self._running:
            try:
                if not self._paused:
                    await self._evaluate_triggers()
                    await self._dispatch_next()
                await asyncio.sleep(self._tick_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("RuntimeScheduler: loop error")
                await asyncio.sleep(max(1.0, self._tick_interval * 10))

    async def _evaluate_triggers(self) -> None:
        """Evaluate active triggers and enqueue ready jobs."""
        if not self._on_trigger:
            return
        try:
            jobs = self._on_trigger()
            for job in jobs:
                if isinstance(job, JobDefinition):
                    self.enqueue(job)
        except Exception:
            logger.exception("RuntimeScheduler: trigger evaluation error")

    async def _dispatch_next(self) -> None:
        """Dispatch the next ready job from the queue."""
        with self._lock:
            if not self._queue or not self._on_dispatch:
                return
            entry = self._queue.pop(0)
        _, _, job = entry

        try:
            result = self._on_dispatch(job)
            self._jobs_dispatched += 1
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            self._dispatch_errors += 1
            logger.exception("RuntimeScheduler: dispatch error for job %s", job.job_id)

    # ── observability ──────────────────────────────────────────────────────

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    @property
    def active_count(self) -> int:
        return len(self._active_jobs)

    @property
    def is_running(self) -> bool:
        return self._running

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for the runtime scheduler."""
        return {
            "running": self._running,
            "paused": self._paused,
            "queue_length": self.queue_length,
            "active_jobs": self.active_count,
            "jobs_processed": self._jobs_processed,
            "jobs_dispatched": self._jobs_dispatched,
            "dispatch_errors": self._dispatch_errors,
            "tick_interval": self._tick_interval,
        }
