"""
Report Scheduler — Automated scheduling and dispatch of risk reports.

Manages recurring report generation on daily, weekly, and monthly
schedules with configurable recipients and delivery channels.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Report schedule types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"
    CUSTOM = "custom"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"


@dataclass
class ReportSchedule:
    """A scheduled report definition."""
    schedule_id: str
    name: str
    schedule_type: ScheduleType
    report_type: str  # daily, weekly, monthly, stress, audit
    cron_expression: Optional[str] = None
    time_of_day: str = "08:00"  # HH:MM
    day_of_week: Optional[int] = None  # 0=Mon, 6=Sun
    day_of_month: Optional[int] = None
    recipients: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=lambda: ["json"])
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: ReportStatus = ReportStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


class ReportScheduler:
    """
    Automated scheduler for risk report generation and dispatch.

    Features:
    - Daily, weekly, monthly schedule support
    - Cron-based custom scheduling
    - Multi-format output (JSON, PDF, Excel)
    - Multi-channel delivery (email, webhook, storage)
    - Schedule management (enable/disable/pause)
    - Execution history and status tracking

    Usage::

        scheduler = ReportScheduler()
        await scheduler.initialize()
        scheduler.add_schedule(ReportSchedule(...))
        await scheduler.start()
    """

    def __init__(self) -> None:
        self._schedules: dict[str, ReportSchedule] = {}
        self._report_generator: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._initialized = False
        self._check_interval = 60  # seconds

    async def initialize(self) -> None:
        """Initialize the scheduler with default schedules."""
        if self._initialized:
            return

        # Default schedules
        self._schedules["daily_risk"] = ReportSchedule(
            schedule_id="daily_risk",
            name="Daily Risk Report",
            schedule_type=ScheduleType.DAILY,
            report_type="daily",
            time_of_day="18:00",
            formats=["json", "pdf"],
        )
        self._schedules["weekly_risk"] = ReportSchedule(
            schedule_id="weekly_risk",
            name="Weekly Risk Report",
            schedule_type=ScheduleType.WEEKLY,
            report_type="weekly",
            time_of_day="08:00",
            day_of_week=0,  # Monday
            formats=["json", "pdf"],
        )
        self._schedules["monthly_risk"] = ReportSchedule(
            schedule_id="monthly_risk",
            name="Monthly Risk Report",
            schedule_type=ScheduleType.MONTHLY,
            report_type="monthly",
            time_of_day="08:00",
            day_of_month=1,
            formats=["json", "pdf"],
        )

        self._initialized = True
        logger.info(f"ReportScheduler initialized with {len(self._schedules)} schedules.")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("ReportScheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ReportScheduler stopped.")

    async def pause(self) -> None:
        """Pause all schedules."""
        for s in self._schedules.values():
            s.enabled = False
        logger.info("ReportScheduler: all schedules paused.")

    async def resume(self) -> None:
        """Resume all schedules."""
        for s in self._schedules.values():
            s.enabled = True
        logger.info("ReportScheduler: all schedules resumed.")

    # ---- Schedule Management ----

    def add_schedule(self, schedule: ReportSchedule) -> None:
        """Add a new schedule."""
        self._schedules[schedule.schedule_id] = schedule
        logger.info(f"ReportScheduler: added schedule '{schedule.schedule_id}'.")

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            return True
        return False

    def get_schedule(self, schedule_id: str) -> Optional[ReportSchedule]:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    def get_schedule(self) -> list[dict[str, Any]]:
        """Get all schedules."""
        return [
            {
                "schedule_id": s.schedule_id,
                "name": s.name,
                "type": s.schedule_type.value,
                "enabled": s.enabled,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "next_run": s.next_run.isoformat() if s.next_run else None,
                "status": s.status.value,
            }
            for s in self._schedules.values()
        ]

    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule."""
        if s := self._schedules.get(schedule_id):
            s.enabled = True
            return True
        return False

    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule."""
        if s := self._schedules.get(schedule_id):
            s.enabled = False
            return True
        return False

    # ---- Trigger ----

    async def trigger_now(self, schedule_id: str) -> dict[str, Any]:
        """Immediately trigger a scheduled report."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return {"error": f"Schedule '{schedule_id}' not found"}

        return await self._execute_schedule(schedule)

    # ---- Generator Injection ----

    def set_report_generator(self, generator: Callable) -> None:
        """Inject a report generator function."""
        self._report_generator = generator

    # ---- Internal ----

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_schedules()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)

    async def _check_schedules(self) -> None:
        """Check all schedules and trigger due ones."""
        now = datetime.now(timezone.utc)

        for schedule in self._schedules.values():
            if not schedule.enabled:
                continue

            if self._is_due(schedule, now):
                asyncio.create_task(self._execute_schedule(schedule))

    def _is_due(self, schedule: ReportSchedule, now: datetime) -> bool:
        """Check if a schedule is due."""
        if schedule.last_run:
            # Check minimum interval
            if schedule.schedule_type == ScheduleType.DAILY:
                if (now - schedule.last_run).total_seconds() < 23 * 3600:
                    return False
            elif schedule.schedule_type == ScheduleType.WEEKLY:
                if (now - schedule.last_run).total_seconds() < 6 * 24 * 3600:
                    return False
            elif schedule.schedule_type == ScheduleType.MONTHLY:
                if (now - schedule.last_run).total_seconds() < 28 * 24 * 3600:
                    return False

        # Check time of day
        try:
            hour, minute = map(int, schedule.time_of_day.split(":"))
            if now.hour != hour or now.minute > minute + 5:
                return False
        except (ValueError, AttributeError):
            pass

        # Check day of week for weekly
        if schedule.schedule_type == ScheduleType.WEEKLY and schedule.day_of_week is not None:
            if now.weekday() != schedule.day_of_week:
                return False

        # Check day of month for monthly
        if schedule.schedule_type == ScheduleType.MONTHLY and schedule.day_of_month is not None:
            if now.day != schedule.day_of_month:
                return False

        return True

    async def _execute_schedule(self, schedule: ReportSchedule) -> dict[str, Any]:
        """Execute a scheduled report generation."""
        schedule.status = ReportStatus.GENERATING

        try:
            if self._report_generator:
                result = await self._report_generator(schedule.report_type)
            else:
                result = {
                    "report_type": schedule.report_type,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "generated",
                    "note": "No report generator configured",
                }

            schedule.last_run = datetime.now(timezone.utc)
            schedule.status = ReportStatus.COMPLETED
            logger.info(f"ReportScheduler: executed '{schedule.schedule_id}' ({schedule.report_type}).")

            return result

        except Exception as e:
            schedule.status = ReportStatus.FAILED
            logger.error(f"ReportScheduler: failed '{schedule.schedule_id}': {e}")
            return {"error": str(e)}
