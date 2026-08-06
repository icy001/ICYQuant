"""Scheduler Service — high-level service layer for the scheduler API.

The :class:`SchedulerService` provides a clean service interface on top
of the engine, handling request validation, error translation, and
orchestration of multi-step operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleStatus
from .models.job import JobDefinition, JobState
from .scheduler_engine import SchedulerEngine
from .scheduler_factory import SchedulerFactory
from .scheduler_validator import validate_schedule_config, ValidationError

logger = logging.getLogger(__name__)


class SchedulerService:
    """High-level service layer for scheduler operations.

    Wraps the scheduler engine with validation, error handling,
    and orchestration logic for multi-step operations.

    Usage::

        svc = SchedulerService(engine)
        result = await svc.register_schedule(data)
    """

    def __init__(self, engine: Optional[SchedulerEngine] = None) -> None:
        self._engine = engine or SchedulerEngine()
        self._factory = SchedulerFactory()
        self._started: bool = False

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize and start the service."""
        if not self._started:
            await self._engine.start()
            self._started = True

    async def shutdown(self) -> None:
        """Shut down the service."""
        if self._started:
            await self._engine.stop()
            self._started = False

    # ── schedule management ────────────────────────────────────────────────

    async def register_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new schedule from configuration data.

        Returns:
            Dict with schedule_id and status, or errors.
        """
        # Validate
        errors = validate_schedule_config(data)
        if errors:
            return {
                "success": False,
                "errors": [e.to_dict() for e in errors],
            }

        # Parse
        from .scheduler_serializer import SchedulerSerializer
        try:
            schedule = SchedulerSerializer.deserialize_schedule(data)
        except Exception as exc:
            return {
                "success": False,
                "errors": [{"field": "parse", "message": str(exc)}],
            }

        # Register
        try:
            registered = await self._engine.register_schedule(schedule)
            return {
                "success": True,
                "schedule_id": registered.schedule_id,
                "status": registered.status.value,
            }
        except ValueError as exc:
            return {
                "success": False,
                "errors": [{"field": "validation", "message": str(exc)}],
            }
        except Exception as exc:
            logger.exception("SchedulerService: register failed")
            return {
                "success": False,
                "errors": [{"field": "internal", "message": str(exc)}],
            }

    async def trigger_schedule(
        self, schedule_id: str, payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Manually trigger a schedule."""
        try:
            job = await self._engine.trigger_manual(schedule_id, payload)
            if job is None:
                return {"success": False, "error": f"Schedule {schedule_id} not found"}
            return {
                "success": True,
                "job_id": job.job_id,
                "state": job.state.value,
            }
        except Exception as exc:
            logger.exception("SchedulerService: trigger failed")
            return {"success": False, "error": str(exc)}

    async def pause_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Pause a schedule."""
        try:
            result = await self._engine.pause_schedule(schedule_id)
            if result is None:
                return {"success": False, "error": f"Schedule {schedule_id} not found"}
            return {"success": True, "schedule_id": schedule_id, "status": result.status.value}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def resume_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Resume a paused schedule."""
        try:
            result = await self._engine.resume_schedule(schedule_id)
            if result is None:
                return {"success": False, "error": f"Schedule {schedule_id} not found"}
            return {"success": True, "schedule_id": schedule_id, "status": result.status.value}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def remove_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Remove a schedule."""
        try:
            result = await self._engine.remove_schedule(schedule_id)
            if result is None:
                return {"success": False, "error": f"Schedule {schedule_id} not found"}
            return {"success": True, "schedule_id": schedule_id}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ── query ──────────────────────────────────────────────────────────────

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a schedule by ID."""
        schedule = self._engine.get_schedule(schedule_id)
        if schedule:
            return schedule.to_dict()
        return None

    def list_schedules(
        self,
        status: Optional[str] = None,
        schedule_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all registered schedules."""
        s_status = ScheduleStatus(status) if status else None
        s_type = ScheduleType(schedule_type) if schedule_type else None
        schedules = self._engine.list_schedules(status=s_status, schedule_type=s_type)
        return [s.to_dict() for s in schedules]

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List current jobs."""
        jobs = self._engine.list_jobs(limit=limit)
        return [j.to_dict() for j in jobs]

    async def get_history(
        self, schedule_id: Optional[str] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve execution history."""
        return await self._engine.get_history(schedule_id=schedule_id, limit=limit)

    # ── factory convenience ────────────────────────────────────────────────

    async def create_cron_schedule(
        self, name: str, cron: str, target: str,
        owner: str = "", description: str = "",
    ) -> Dict[str, Any]:
        """Create and register a cron schedule from a factory template."""
        schedule = self._factory.cron_schedule(
            name=name, cron=cron, target=target,
            owner=owner, description=description,
        )
        registered = await self._engine.register_schedule(schedule)
        return {
            "success": True,
            "schedule_id": registered.schedule_id,
            "status": registered.status.value,
        }

    # ── observability ──────────────────────────────────────────────────────

    def health_report(self) -> Dict[str, Any]:
        """Produce a service health report."""
        return {
            "started": self._started,
            "engine": self._engine.health_report(),
        }
