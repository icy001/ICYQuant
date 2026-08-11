"""
ICYQuant Retraining Scheduler — Scheduled and cron-based retraining.

Manages periodic retraining according to:
  - Fixed intervals (daily, weekly, monthly)
  - Cron expressions
  - Market calendar events (after close, before open)
  - Data availability events (new data published)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ScheduleType(str, Enum):
    """Type of schedule."""
    INTERVAL = "interval"       # Every N hours/days
    CRON = "cron"               # Cron expression
    DAILY_AT = "daily_at"       # Daily at specific time
    WEEKLY_AT = "weekly_at"     # Weekly on specific day
    AFTER_MARKET_CLOSE = "after_market_close"
    BEFORE_MARKET_OPEN = "before_market_open"
    ON_DATA_UPDATE = "on_data_update"


@dataclass
class RetrainSchedule:
    """A retraining schedule entry."""
    model_id: str
    schedule_type: ScheduleType
    interval_hours: Optional[float] = None
    cron_expression: Optional[str] = None
    time_of_day: Optional[str] = None    # "HH:MM" format
    day_of_week: Optional[int] = None    # 0=Monday, 6=Sunday
    timezone: str = "UTC"
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Retraining Scheduler
# ---------------------------------------------------------------------------

class RetrainingScheduler:
    """Scheduled retraining manager.

    Usage::

        scheduler = RetrainingScheduler(retraining_manager)
        scheduler.schedule_daily("nvda_model", time="23:00")
        await scheduler.start()
    """

    def __init__(self, retraining_manager):
        self.retraining_manager = retraining_manager
        self._initialized = False
        self._running = False

        # Schedules
        self._schedules: Dict[str, List[RetrainSchedule]] = {}

        # Background loop
        self._check_interval: int = 60  # seconds
        self._task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RetrainingScheduler initialized")

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("RetrainingScheduler started — check every %ds", self._check_interval)

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("RetrainingScheduler stopped")

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    def schedule_daily(self, model_id: str, time: str = "00:00") -> RetrainSchedule:
        """Schedule daily retraining at a specific time."""
        schedule = RetrainSchedule(
            model_id=model_id,
            schedule_type=ScheduleType.DAILY_AT,
            time_of_day=time,
            next_run_at=self._compute_next_daily_run(time),
        )
        self._add_schedule(model_id, schedule)
        return schedule

    def schedule_weekly(
        self, model_id: str, day_of_week: int, time: str = "00:00"
    ) -> RetrainSchedule:
        """Schedule weekly retraining."""
        schedule = RetrainSchedule(
            model_id=model_id,
            schedule_type=ScheduleType.WEEKLY_AT,
            day_of_week=day_of_week,
            time_of_day=time,
        )
        self._add_schedule(model_id, schedule)
        return schedule

    def schedule_interval(
        self, model_id: str, interval_hours: float
    ) -> RetrainSchedule:
        """Schedule retraining at fixed intervals."""
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=interval_hours)
        schedule = RetrainSchedule(
            model_id=model_id,
            schedule_type=ScheduleType.INTERVAL,
            interval_hours=interval_hours,
            next_run_at=next_run.isoformat(),
        )
        self._add_schedule(model_id, schedule)
        return schedule

    def schedule_after_market_close(self, model_id: str) -> RetrainSchedule:
        """Schedule retraining after market close (~16:30 EST)."""
        schedule = RetrainSchedule(
            model_id=model_id,
            schedule_type=ScheduleType.AFTER_MARKET_CLOSE,
            time_of_day="21:30",  # UTC after US market close
        )
        self._add_schedule(model_id, schedule)
        return schedule

    def remove_schedule(self, model_id: str, schedule_type: ScheduleType) -> bool:
        """Remove all schedules of a type for a model."""
        if model_id not in self._schedules:
            return False
        before = len(self._schedules[model_id])
        self._schedules[model_id] = [
            s for s in self._schedules[model_id]
            if s.schedule_type != schedule_type
        ]
        return len(self._schedules[model_id]) < before

    def get_schedules(self, model_id: str) -> List[RetrainSchedule]:
        return self._schedules.get(model_id, [])

    def list_all_schedules(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            mid: [
                {
                    "schedule_type": s.schedule_type.value,
                    "time_of_day": s.time_of_day,
                    "interval_hours": s.interval_hours,
                    "enabled": s.enabled,
                    "last_run_at": s.last_run_at,
                    "next_run_at": s.next_run_at,
                }
                for s in schedules
            ]
            for mid, schedules in self._schedules.items()
        }

    # ------------------------------------------------------------------
    # Scheduler loop
    # ------------------------------------------------------------------

    async def _scheduler_loop(self) -> None:
        """Background loop that checks and triggers scheduled retraining."""
        while self._running:
            try:
                await self._check_due_schedules()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler loop error")
                await asyncio.sleep(self._check_interval)

    async def _check_due_schedules(self) -> None:
        """Check all schedules and trigger due ones."""
        now = datetime.now(timezone.utc)

        for model_id, schedules in self._schedules.items():
            for schedule in schedules:
                if not schedule.enabled:
                    continue

                if not self._is_due(schedule, now):
                    continue

                # Trigger retraining
                try:
                    logger.info(
                        "Scheduled retraining for %s (type=%s)",
                        model_id, schedule.schedule_type.value,
                    )
                    from .retraining_manager import TriggerReason
                    await self.retraining_manager.trigger(
                        model_id=model_id,
                        reason=TriggerReason.SCHEDULED,
                    )
                    schedule.last_run_at = now.isoformat()
                    schedule.next_run_at = self._compute_next_run(schedule, now)
                except Exception as exc:
                    logger.error(
                        "Scheduled retraining failed for %s: %s",
                        model_id, exc,
                    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_schedule(self, model_id: str, schedule: RetrainSchedule) -> None:
        if model_id not in self._schedules:
            self._schedules[model_id] = []
        self._schedules[model_id].append(schedule)

    def _is_due(self, schedule: RetrainSchedule, now: datetime) -> bool:
        """Check if a schedule is due to run."""
        if schedule.next_run_at is None:
            return False

        next_run = datetime.fromisoformat(schedule.next_run_at)
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        return now >= next_run

    def _compute_next_run(
        self, schedule: RetrainSchedule, reference: datetime
    ) -> str:
        """Compute the next run time."""
        if schedule.schedule_type == ScheduleType.INTERVAL and schedule.interval_hours:
            next_run = reference + timedelta(hours=schedule.interval_hours)
        elif schedule.schedule_type == ScheduleType.DAILY_AT and schedule.time_of_day:
            next_run = reference + timedelta(days=1)
            next_run = self._set_time(next_run, schedule.time_of_day)
        else:
            next_run = reference + timedelta(hours=24)

        return next_run.isoformat()

    @staticmethod
    def _compute_next_daily_run(time_str: str) -> str:
        """Compute next daily run time."""
        now = datetime.now(timezone.utc)
        target = RetrainingScheduler._set_time(now, time_str)
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    @staticmethod
    def _set_time(dt: datetime, time_str: str) -> datetime:
        """Set the time on a datetime object."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            return dt.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        except ValueError:
            return dt

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "running": self._running,
            "total_models": len(self._schedules),
            "total_schedules": sum(len(s) for s in self._schedules.values()),
        }

    def __repr__(self) -> str:
        return f"RetrainingScheduler(schedules={sum(len(s) for s in self._schedules.values())})"
