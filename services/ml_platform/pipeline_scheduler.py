"""
ICYQuant Pipeline Scheduler - Automated ML pipeline scheduling.

Schedules recurring ML pipeline runs:
- Daily feature recomputation
- Weekly model retraining
- Monthly model evaluation
- Drift-based trigger retraining
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Schedule types."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    HOURLY = "hourly"
    CUSTOM = "custom"
    ON_DEMAND = "on_demand"
    EVENT_TRIGGERED = "event_triggered"


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled pipeline."""

    schedule_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    schedule_type: ScheduleType = ScheduleType.DAILY

    # Timing
    cron_expression: str = ""     # e.g. "0 6 * * 1-5" (weekdays 6AM)
    time_of_day: str = "06:00"    # HH:MM
    day_of_week: int = 0          # 0=Monday, 6=Sunday
    day_of_month: int = 1

    # Pipeline
    pipeline_function: Optional[Callable] = None
    pipeline_args: Dict[str, Any] = field(default_factory=dict)

    # Retry
    max_retries: int = 3
    retry_delay_seconds: int = 300
    timeout_seconds: int = 7200

    # Status
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    # Notification
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notify_channels: List[str] = field(default_factory=list)


@dataclass
class ScheduledRun:
    """Record of a scheduled pipeline execution."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    schedule_id: str = ""
    status: str = "pending"  # pending, running, completed, failed

    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    error: Optional[str] = None
    result: Optional[Any] = None


class PipelineScheduler:
    """Schedules and manages recurring ML pipeline runs.

    Supports:
    - Time-based scheduling (daily, weekly, monthly)
    - Cron-based scheduling
    - Event-triggered scheduling (drift detection)
    - Retry with backoff
    - Execution history tracking
    """

    def __init__(self) -> None:
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._run_history: List[ScheduledRun] = []
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    # -- Registration --

    def register_schedule(self, config: ScheduleConfig) -> str:
        """Register a new scheduled pipeline."""
        config.next_run = self._compute_next_run(config)
        self._schedules[config.schedule_id] = config
        logger.info("Schedule registered: %s (%s, next=%s)",
                     config.schedule_id, config.name, config.next_run)
        return config.schedule_id

    def _compute_next_run(self, config: ScheduleConfig) -> datetime:
        """Compute the next run time for a schedule."""
        now = datetime.utcnow()

        if config.schedule_type == ScheduleType.DAILY:
            target = now.replace(hour=int(config.time_of_day[:2]), minute=int(config.time_of_day[3:]), second=0)
            if target <= now:
                target += timedelta(days=1)
            return target

        elif config.schedule_type == ScheduleType.WEEKLY:
            target = now.replace(hour=int(config.time_of_day[:2]), minute=int(config.time_of_day[3:]), second=0)
            days_ahead = config.day_of_week - target.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return target + timedelta(days=days_ahead)

        elif config.schedule_type == ScheduleType.MONTHLY:
            target = now.replace(day=config.day_of_month, hour=int(config.time_of_day[:2]),
                                  minute=int(config.time_of_day[3:]), second=0)
            if target <= now:
                # Move to next month
                if now.month == 12:
                    target = target.replace(year=now.year + 1, month=1)
                else:
                    target = target.replace(month=now.month + 1)
            return target

        elif config.schedule_type == ScheduleType.HOURLY:
            target = now.replace(minute=0, second=0) + timedelta(hours=1)
            return target

        else:
            return now + timedelta(days=1)

    # -- Lifecycle --

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._loop())
        logger.info("Pipeline Scheduler started (%d schedules)", len(self._schedules))

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        logger.info("Pipeline Scheduler stopped")

    async def _loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()
                for config in self._schedules.values():
                    if config.enabled and config.next_run and config.next_run <= now:
                        await self._trigger_run(config)
                        config.next_run = self._compute_next_run(config)
            except Exception as exc:
                logger.exception("Scheduler loop error: %s", exc)

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _trigger_run(self, config: ScheduleConfig) -> None:
        """Trigger a scheduled pipeline run."""
        run = ScheduledRun(schedule_id=config.schedule_id)
        run.status = "running"
        run.started_at = datetime.utcnow()

        config.last_run = run.started_at
        logger.info("Scheduled run triggered: %s (%s)", run.run_id, config.name)

        try:
            if config.pipeline_function:
                result = await asyncio.wait_for(
                    config.pipeline_function(**config.pipeline_args)
                    if asyncio.iscoroutinefunction(config.pipeline_function)
                    else asyncio.to_thread(config.pipeline_function, **config.pipeline_args),
                    timeout=config.timeout_seconds,
                )
                run.result = result

            run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            logger.error("Scheduled run failed: %s", exc)
        finally:
            run.completed_at = datetime.utcnow()
            if run.started_at:
                run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
            self._run_history.append(run)

    # -- Management --

    def get_schedule(self, schedule_id: str) -> Optional[ScheduleConfig]:
        return self._schedules.get(schedule_id)

    def get_run_history(self, schedule_id: str, limit: int = 20) -> List[ScheduledRun]:
        """Get run history for a schedule."""
        runs = [r for r in self._run_history if r.schedule_id == schedule_id]
        return sorted(runs, key=lambda r: r.scheduled_at, reverse=True)[:limit]

    def enable_schedule(self, schedule_id: str) -> bool:
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = True
            schedule.next_run = self._compute_next_run(schedule)
            return True
        return False

    def disable_schedule(self, schedule_id: str) -> bool:
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.enabled = False
            return True
        return False

    async def trigger_now(self, schedule_id: str) -> Optional[str]:
        """Manually trigger a schedule immediately."""
        config = self._schedules.get(schedule_id)
        if config is None:
            return None
        await self._trigger_run(config)
        return schedule_id
