"""Runtime Manager — central coordinator for scheduler runtime lifecycle.

The :class:`RuntimeManager` maintains the complete runtime state of the
scheduler, including job instances, execution contexts, runtime variables,
and scheduler state.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .runtime_state import RuntimeStateManager, RuntimePhase
from .runtime_context import SchedulerContext
from .runtime_events import SchedulerEventBus, SchedulerEventType

logger = logging.getLogger(__name__)


class RuntimeState(str, enum.Enum):
    """Runtime manager lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    DEGRADED = "degraded"
    ERROR = "error"


class RuntimeManager:
    """Manages the complete scheduler runtime lifecycle.

    Coordinates runtime state, contexts, events, and metrics subsystems.
    Provides the single entry point for starting/stopping/pausing the
    scheduler runtime.

    Usage::

        manager = RuntimeManager()
        await manager.start()
        ctx = manager.create_context(schedule_id="sch_001", trace_id="trace_abc")
        await manager.stop()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: RuntimeState = RuntimeState.STOPPED
        self._state_manager = RuntimeStateManager()
        self._event_bus = SchedulerEventBus()
        self._contexts: Dict[str, SchedulerContext] = {}
        self._active_jobs: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {}
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self._on_start_callbacks: List[Callable[[], None]] = []
        self._on_stop_callbacks: List[Callable[[], None]] = []

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the scheduler runtime."""
        with self._lock:
            if self._state == RuntimeState.RUNNING:
                return
            self._state = RuntimeState.STARTING

        logger.info("RuntimeManager: starting scheduler runtime")
        self._state_manager.transition(RuntimePhase.INITIALIZING)
        self._event_bus.start()
        self._started_at = datetime.now(timezone.utc)

        for cb in self._on_start_callbacks:
            try:
                cb()
            except Exception:
                logger.exception("RuntimeManager: start callback failed")

        with self._lock:
            self._state = RuntimeState.RUNNING
            self._state_manager.transition(RuntimePhase.ACTIVE)

        logger.info("RuntimeManager: scheduler runtime started")

    async def stop(self) -> None:
        """Gracefully stop the scheduler runtime."""
        with self._lock:
            if self._state in (RuntimeState.STOPPED, RuntimeState.STOPPING):
                return
            self._state = RuntimeState.STOPPING

        logger.info("RuntimeManager: stopping scheduler runtime")
        self._state_manager.transition(RuntimePhase.SHUTTING_DOWN)

        for cb in self._on_stop_callbacks:
            try:
                cb()
            except Exception:
                logger.exception("RuntimeManager: stop callback failed")

        self._event_bus.stop()
        self._contexts.clear()
        self._active_jobs.clear()

        with self._lock:
            self._state = RuntimeState.STOPPED
            self._state_manager.transition(RuntimePhase.TERMINATED)
            self._stopped_at = datetime.now(timezone.utc)

        logger.info("RuntimeManager: scheduler runtime stopped")

    async def pause(self) -> None:
        """Pause scheduling (running jobs continue)."""
        with self._lock:
            if self._state != RuntimeState.RUNNING:
                return
            self._state = RuntimeState.PAUSED
            self._state_manager.transition(RuntimePhase.PAUSED)
        logger.info("RuntimeManager: scheduler runtime paused")

    async def resume(self) -> None:
        """Resume scheduling after pause."""
        with self._lock:
            if self._state != RuntimeState.PAUSED:
                return
            self._state = RuntimeState.RUNNING
            self._state_manager.transition(RuntimePhase.ACTIVE)
        logger.info("RuntimeManager: scheduler runtime resumed")

    # ── context management ─────────────────────────────────────────────────

    def create_context(
        self,
        schedule_id: str,
        trace_id: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> SchedulerContext:
        """Create a new scheduler execution context."""
        ctx = SchedulerContext(
            schedule_id=schedule_id,
            trace_id=trace_id or f"trace_{schedule_id}",
            job_id=job_id,
            variables=kwargs,
        )
        with self._lock:
            self._contexts[ctx.execution_id] = ctx
        return ctx

    def get_context(self, execution_id: str) -> Optional[SchedulerContext]:
        """Retrieve an active context by ID."""
        return self._contexts.get(execution_id)

    def remove_context(self, execution_id: str) -> Optional[SchedulerContext]:
        """Remove and return a completed context."""
        with self._lock:
            return self._contexts.pop(execution_id, None)

    # ── job tracking ───────────────────────────────────────────────────────

    def register_job(self, job_id: str, job_data: Any) -> None:
        """Register an active job in the runtime."""
        with self._lock:
            self._active_jobs[job_id] = job_data

    def unregister_job(self, job_id: str) -> Optional[Any]:
        """Remove a completed job from the runtime."""
        with self._lock:
            return self._active_jobs.pop(job_id, None)

    def get_active_jobs(self) -> Dict[str, Any]:
        """Return a snapshot of all active jobs."""
        with self._lock:
            return dict(self._active_jobs)

    # ── lifecycle callbacks ────────────────────────────────────────────────

    def on_start(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked on runtime start."""
        self._on_start_callbacks.append(callback)

    def on_stop(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked on runtime stop."""
        self._on_stop_callbacks.append(callback)

    # ── observability ──────────────────────────────────────────────────────

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == RuntimeState.RUNNING

    @property
    def active_context_count(self) -> int:
        return len(self._contexts)

    @property
    def active_job_count(self) -> int:
        return len(self._active_jobs)

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for the runtime manager."""
        return {
            "state": self._state.value,
            "active_contexts": self.active_context_count,
            "active_jobs": self.active_job_count,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "stopped_at": self._stopped_at.isoformat() if self._stopped_at else None,
            "state_manager": self._state_manager.health_report(),
        }
