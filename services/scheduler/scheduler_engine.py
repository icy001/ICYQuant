"""Unified Scheduler Engine — top-level entry point for distributed scheduling.

The :class:`SchedulerEngine` is the single entry point that coordinates:

* Job scheduling (register → validate → persist → trigger → dispatch)
* Trigger evaluation (when to fire)
* Resource allocation (where to run)
* Execution dispatch (who to send to)

Architecture::

    SchedulerEngine
          │
    SchedulerManager
          │
    ┌──────┼──────┐
    Registry  Runtime  Repository
    └──────┼──────┘
    SchedulerRuntime → Workflow Engine
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .scheduler_manager import SchedulerManager
from .scheduler_registry import SchedulerRegistry
from .scheduler_runtime import SchedulerRuntime
from .scheduler_repository import SchedulerRepository
from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleStatus
from .models.job import JobDefinition, JobState, JobPriority

logger = logging.getLogger(__name__)


class EngineState:
    """Scheduler engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class SchedulerEngine:
    """Top-level entry point for the ICYQuant distributed scheduler.

    The engine wires together the Manager, Registry, Runtime, and
    Repository layers and provides a single API for registering,
    scheduling, and managing distributed jobs.

    Usage::

        engine = SchedulerEngine()
        await engine.start()
        await engine.register_schedule(schedule_def)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: str = EngineState.UNINITIALIZED
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

        # Core components
        self._registry = SchedulerRegistry()
        self._repository = SchedulerRepository()
        self._manager: Optional[SchedulerManager] = None
        self._runtime: Optional[SchedulerRuntime] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the scheduler engine."""
        with self._lock:
            if self._state in (EngineState.RUNNING, EngineState.READY):
                return
            self._state = EngineState.INITIALIZING

        logger.info("SchedulerEngine: initializing")

        # Initialize repository
        await self._repository.initialize()

        # Wire up manager
        self._manager = SchedulerManager(
            registry=self._registry,
            repository=self._repository,
        )
        await self._manager.start()

        # Wire up runtime
        self._runtime = SchedulerRuntime(
            registry=self._registry,
            repository=self._repository,
            manager=self._manager,
        )
        await self._runtime.start()

        with self._lock:
            self._state = EngineState.READY
            self._started_at = datetime.now(timezone.utc)

        logger.info("SchedulerEngine: ready")

        # Transition to running
        with self._lock:
            self._state = EngineState.RUNNING

    async def stop(self) -> None:
        """Gracefully stop the scheduler engine."""
        with self._lock:
            if self._state in (EngineState.STOPPED, EngineState.STOPPING):
                return
            self._state = EngineState.STOPPING

        logger.info("SchedulerEngine: stopping")

        if self._runtime:
            await self._runtime.stop()
        if self._manager:
            await self._manager.stop()
        await self._repository.shutdown()

        with self._lock:
            self._state = EngineState.STOPPED
            self._stopped_at = datetime.now(timezone.utc)

        logger.info("SchedulerEngine: stopped")

    async def pause(self) -> None:
        """Pause scheduling."""
        with self._lock:
            if self._state != EngineState.RUNNING:
                return
            self._state = EngineState.PAUSED
        if self._runtime:
            await self._runtime.pause()
        logger.info("SchedulerEngine: paused")

    async def resume(self) -> None:
        """Resume scheduling."""
        with self._lock:
            if self._state != EngineState.PAUSED:
                return
            self._state = EngineState.RUNNING
        if self._runtime:
            await self._runtime.resume()
        logger.info("SchedulerEngine: resumed")

    # ── schedule management ────────────────────────────────────────────────

    async def register_schedule(self, schedule: ScheduleDefinition) -> ScheduleDefinition:
        """Register a new schedule definition."""
        validated = self._registry.register(schedule)
        await self._repository.save_schedule(validated)
        if self._runtime:
            await self._runtime.on_schedule_registered(validated)
        return validated

    async def pause_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Pause an active schedule."""
        schedule = self._registry.pause(schedule_id)
        if schedule:
            await self._repository.save_schedule(schedule)
            if self._runtime:
                await self._runtime.on_schedule_paused(schedule)
        return schedule

    async def resume_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Resume a paused schedule."""
        schedule = self._registry.resume(schedule_id)
        if schedule:
            await self._repository.save_schedule(schedule)
            if self._runtime:
                await self._runtime.on_schedule_resumed(schedule)
        return schedule

    async def remove_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Remove a schedule definition."""
        schedule = self._registry.remove(schedule_id)
        if schedule:
            await self._repository.delete_schedule(schedule_id)
            if self._runtime:
                await self._runtime.on_schedule_removed(schedule)
        return schedule

    async def trigger_manual(self, schedule_id: str, payload: Optional[Dict[str, Any]] = None) -> Optional[JobDefinition]:
        """Manually trigger a schedule (fire immediately)."""
        schedule = self._registry.get(schedule_id)
        if schedule is None:
            logger.warning("SchedulerEngine: schedule %s not found", schedule_id)
            return None
        job = JobDefinition(
            job_id=f"job_manual_{schedule_id}_{int(datetime.now(timezone.utc).timestamp())}",
            schedule_id=schedule_id,
            target=schedule.target,
            trigger_type="manual",
            priority=JobPriority.HIGH,
            payload=payload or schedule.payload,
        )
        if self._runtime:
            await self._runtime.enqueue_job(job)
        return job

    # ── query ──────────────────────────────────────────────────────────────

    def get_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Retrieve a schedule definition by ID."""
        return self._registry.get(schedule_id)

    def list_schedules(
        self,
        status: Optional[ScheduleStatus] = None,
        schedule_type: Optional[ScheduleType] = None,
    ) -> List[ScheduleDefinition]:
        """List all registered schedules, optionally filtered."""
        return self._registry.list_all(status=status, schedule_type=schedule_type)

    def get_job(self, job_id: str) -> Optional[JobDefinition]:
        """Retrieve a job by ID."""
        if self._runtime:
            return self._runtime.get_job(job_id)
        if self._manager:
            return self._manager.get_job(job_id)
        return None

    def list_jobs(self, limit: int = 100) -> List[JobDefinition]:
        """List active/queued jobs."""
        if self._runtime:
            return self._runtime.list_jobs(limit=limit)
        return []

    async def get_history(
        self, schedule_id: Optional[str] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve execution history."""
        return await self._repository.get_history(schedule_id=schedule_id, limit=limit)

    # ── observability ──────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == EngineState.RUNNING

    @property
    def uptime_seconds(self) -> float:
        if not self._started_at:
            return 0.0
        return (datetime.now(timezone.utc) - self._started_at).total_seconds()

    def health_report(self) -> Dict[str, Any]:
        """Produce a comprehensive health report."""
        report: Dict[str, Any] = {
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "stopped_at": self._stopped_at.isoformat() if self._stopped_at else None,
            "uptime_seconds": self.uptime_seconds,
            "registry": self._registry.health_report(),
            "repository": self._repository.health_report(),
        }
        if self._manager:
            report["manager"] = self._manager.health_report()
        if self._runtime:
            report["runtime"] = self._runtime.health_report()
        return report
