"""Scheduler API — REST endpoints for the distributed scheduler.

Provides a unified REST API for:
* Schedule registration and lifecycle management
* Manual trigger and pause/resume operations
* Job and execution history queries
* Health and metrics endpoints
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .scheduler_service import SchedulerService

logger = logging.getLogger(__name__)


class SchedulerAPI:
    """REST API handler for scheduler operations.

    Provides method handlers for HTTP routes. Designed to be used
    with any ASGI framework (FastAPI, Starlette, etc.).

    Usage::

        api = SchedulerAPI(service)
        # Register routes in FastAPI:
        app.post("/scheduler/register")(api.register_schedule)
        app.get("/scheduler/jobs")(api.list_jobs)
    """

    def __init__(self, service: Optional[SchedulerService] = None) -> None:
        self._service = service or SchedulerService()

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the API service."""
        await self._service.initialize()

    async def shutdown(self) -> None:
        """Shut down the API service."""
        await self._service.shutdown()

    # ── schedule endpoints ─────────────────────────────────────────────────

    async def register_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /scheduler/register

        Register a new schedule definition.
        """
        logger.info("API: register_schedule %s", data.get("schedule_id", "unknown"))
        return await self._service.register_schedule(data)

    async def trigger_schedule(
        self, schedule_id: str, payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /scheduler/trigger/{schedule_id}

        Manually trigger a schedule.
        """
        logger.info("API: trigger_schedule %s", schedule_id)
        return await self._service.trigger_schedule(schedule_id, payload)

    async def pause_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """POST /scheduler/pause/{schedule_id}

        Pause an active schedule.
        """
        logger.info("API: pause_schedule %s", schedule_id)
        return await self._service.pause_schedule(schedule_id)

    async def resume_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """POST /scheduler/resume/{schedule_id}

        Resume a paused schedule.
        """
        logger.info("API: resume_schedule %s", schedule_id)
        return await self._service.resume_schedule(schedule_id)

    async def remove_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """DELETE /scheduler/remove/{schedule_id}

        Remove a schedule definition.
        """
        logger.info("API: remove_schedule %s", schedule_id)
        return await self._service.remove_schedule(schedule_id)

    # ── query endpoints ────────────────────────────────────────────────────

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """GET /scheduler/{schedule_id}

        Retrieve a schedule by ID.
        """
        return self._service.get_schedule(schedule_id)

    def list_schedules(
        self,
        status: Optional[str] = None,
        schedule_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """GET /scheduler/list

        List all registered schedules, optionally filtered.

        Query params:
            status: Filter by status (active/paused/draft/etc.)
            schedule_type: Filter by type (cron/interval/oneshot/etc.)
        """
        return self._service.list_schedules(status=status, schedule_type=schedule_type)

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """GET /scheduler/jobs

        List current active and queued jobs.

        Query params:
            limit: Max number of jobs to return (default 100).
        """
        return self._service.list_jobs(limit=limit)

    async def get_history(
        self,
        schedule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """GET /scheduler/history

        Retrieve execution history.

        Query params:
            schedule_id: Optional filter by schedule.
            limit: Max records to return (default 100).
        """
        return await self._service.get_history(schedule_id=schedule_id, limit=limit)

    # ── observability endpoints ────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """GET /scheduler/health

        Return a comprehensive health report.
        """
        return self._service.health_report()

    def list_routes(self) -> List[Dict[str, str]]:
        """Return a list of available API routes (for discovery)."""
        return [
            {"method": "POST", "path": "/scheduler/register", "description": "Register a new schedule"},
            {"method": "POST", "path": "/scheduler/trigger/{schedule_id}", "description": "Manually trigger a schedule"},
            {"method": "POST", "path": "/scheduler/pause/{schedule_id}", "description": "Pause a schedule"},
            {"method": "POST", "path": "/scheduler/resume/{schedule_id}", "description": "Resume a paused schedule"},
            {"method": "DELETE", "path": "/scheduler/remove/{schedule_id}", "description": "Remove a schedule"},
            {"method": "GET", "path": "/scheduler/{schedule_id}", "description": "Get schedule details"},
            {"method": "GET", "path": "/scheduler/list", "description": "List all schedules"},
            {"method": "GET", "path": "/scheduler/jobs", "description": "List active jobs"},
            {"method": "GET", "path": "/scheduler/history", "description": "Get execution history"},
            {"method": "GET", "path": "/scheduler/health", "description": "Health check"},
        ]
