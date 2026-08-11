"""
Risk Scheduler — Scheduled risk evaluation execution.

Manages periodic risk checks, cron-based evaluation triggers,
and batch evaluation scheduling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Schedule trigger types."""
    CRON = "cron"
    INTERVAL = "interval"
    EVENT_DRIVEN = "event_driven"
    MANUAL = "manual"


class ScheduleStatus(str, Enum):
    """Schedule status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RiskSchedule:
    """Definition of a scheduled risk evaluation."""
    schedule_id: str
    name: str
    schedule_type: ScheduleType
    cron_expression: str = ""
    interval_seconds: float = 0.0
    policy_ids: list[str] = field(default_factory=list)
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskScheduler:
    """
    Scheduler for recurring risk evaluations.

    Supports cron-based, interval-based, event-driven, and manual
    trigger types for periodic risk checks.

    Usage::

        scheduler = RiskScheduler()
        await scheduler.initialize()
        schedule = await scheduler.create(RiskSchedule(
            schedule_id="hourly_check",
            name="Hourly Risk Check",
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
        ))
        await scheduler.start()
    """

    def __init__(self) -> None:
        self._schedules: dict[str, RiskSchedule] = {}
        self._running: bool = False

    async def initialize(self) -> None:
        """Initialize the risk scheduler."""
        logger.info("RiskScheduler initialized.")

    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        logger.info("RiskScheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("RiskScheduler stopped.")

    # ---- Schedule Management ----

    async def create(self, schedule: RiskSchedule) -> RiskSchedule:
        """Create a new risk evaluation schedule."""
        self._schedules[schedule.schedule_id] = schedule
        logger.info(f"Risk schedule created: {schedule.schedule_id} ({schedule.schedule_type.value})")
        return schedule

    async def delete(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            return True
        return False

    async def pause(self, schedule_id: str) -> bool:
        """Pause a schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.PAUSED
        return True

    async def resume(self, schedule_id: str) -> bool:
        """Resume a paused schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.ACTIVE
        return True

    async def trigger_now(self, schedule_id: str) -> Optional[dict[str, Any]]:
        """Trigger an immediate evaluation."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        schedule.last_run_at = datetime.now(timezone.utc)
        return {"schedule_id": schedule_id, "triggered_at": schedule.last_run_at.isoformat()}

    # ---- Query ----

    async def get(self, schedule_id: str) -> Optional[RiskSchedule]:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    async def list_active(self) -> list[RiskSchedule]:
        """List all active schedules."""
        return [s for s in self._schedules.values() if s.status == ScheduleStatus.ACTIVE]

    async def list_all(self) -> list[RiskSchedule]:
        """List all schedules."""
        return list(self._schedules.values())

    async def health_check(self) -> dict[str, Any]:
        """Check scheduler health."""
        return {
            "status": "running" if self._running else "stopped",
            "active_schedules": len(await self.list_active()),
            "total_schedules": len(self._schedules),
        }
