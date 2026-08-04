"""
Rotation scheduler.

Manages scheduled rotation tasks
with support for cron-like schedules,
interval-based triggers, lease
expiration, and custom policy
driven execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .policy import RotationPolicy

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Schedule trigger types."""

    CRON = "cron"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    LEASE_BASED = "lease_based"
    EXPIRATION_BASED = "expiration_based"
    ON_DEMAND = "on_demand"


@dataclass
class ScheduleEntry:
    """
    A scheduled rotation entry.

    Attributes:
        schedule_id: Unique schedule identifier.
        secret_key: Target secret key.
        schedule_type: Type of schedule.
        interval_seconds: Interval for interval-based schedules.
        cron_expression: Cron expression for cron schedules.
        policy: Associated rotation policy.
        last_run_at: Last execution timestamp.
        next_run_at: Next scheduled execution.
        enabled: Whether the schedule is active.
        run_count: Total execution count.
        failure_count: Consecutive failure count.
    """

    schedule_id: str = ""
    secret_key: str = ""
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    interval_seconds: int = 86400
    cron_expression: str = ""
    policy: Optional[RotationPolicy] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    enabled: bool = True
    run_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_next_run(
        self,
        now: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate the next run time.

        Args:
            now: Current timestamp.

        Returns:
            Next scheduled execution.
        """
        if now is None:
            now = datetime.utcnow()

        if self.last_run_at:
            base = self.last_run_at
        else:
            base = now

        if self.schedule_type == ScheduleType.INTERVAL:
            return base + timedelta(seconds=self.interval_seconds)
        elif self.schedule_type == ScheduleType.DAILY:
            next_run = base + timedelta(days=1)
            return next_run.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.schedule_type == ScheduleType.WEEKLY:
            next_run = base + timedelta(weeks=1)
            return next_run.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.schedule_type == ScheduleType.MONTHLY:
            # Approximate: 30 days
            return base + timedelta(days=30)
        else:
            return base + timedelta(seconds=self.interval_seconds)

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """Check if the schedule is due for execution."""
        if not self.enabled:
            return False
        if self.next_run_at is None:
            return True
        if now is None:
            now = datetime.utcnow()
        return now >= self.next_run_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "secret_key": self.secret_key,
            "schedule_type": self.schedule_type.value,
            "interval_seconds": self.interval_seconds,
            "last_run_at": (
                self.last_run_at.isoformat() + "Z"
                if self.last_run_at
                else None
            ),
            "next_run_at": (
                self.next_run_at.isoformat() + "Z"
                if self.next_run_at
                else None
            ),
            "enabled": self.enabled,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
        }


class RotationScheduler:
    """
    Rotation task scheduler.

    Manages the scheduling and execution
    of rotation tasks, supporting multiple
    schedule types and automatic retry
    logic for failed rotations.

    Usage:
        scheduler = RotationScheduler()
        scheduler.add_schedule(
            secret_key="database/password",
            schedule_type=ScheduleType.DAILY,
        )
        await scheduler.start()
    """

    MAX_FAILURES = 5
    CHECK_INTERVAL_SECONDS = 60

    def __init__(
        self,
        execute_fn: Optional[Callable] = None,
        on_schedule: Optional[Callable] = None,
    ) -> None:
        """
        Initialize scheduler.

        Args:
            execute_fn: Function to execute rotations.
            on_schedule: Callback for schedule execution.
        """
        self._execute_fn = execute_fn
        self._on_schedule = on_schedule
        self._schedules: Dict[str, ScheduleEntry] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = self.CHECK_INTERVAL_SECONDS

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def add_schedule(
        self,
        secret_key: str,
        schedule_type: ScheduleType = ScheduleType.INTERVAL,
        interval_seconds: int = 86400,
        policy: Optional[RotationPolicy] = None,
        cron_expression: str = "",
    ) -> ScheduleEntry:
        """
        Add a rotation schedule.

        Args:
            secret_key: Secret key to rotate.
            schedule_type: Type of schedule.
            interval_seconds: Interval between rotations.
            policy: Rotation policy to apply.
            cron_expression: Cron expression for cron schedules.

        Returns:
            Created ScheduleEntry.
        """
        import uuid

        entry = ScheduleEntry(
            schedule_id=uuid.uuid4().hex[:12],
            secret_key=secret_key,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            policy=policy,
            cron_expression=cron_expression,
            next_run_at=datetime.utcnow(),
        )

        self._schedules[entry.schedule_id] = entry
        logger.info(
            "Schedule added: %s (%s, type=%s)",
            secret_key, entry.schedule_id, schedule_type.value,
        )

        return entry

    def add_daily_schedule(
        self,
        secret_key: str,
        hour: int = 2,
        minute: int = 0,
        policy: Optional[RotationPolicy] = None,
    ) -> ScheduleEntry:
        """
        Add a daily rotation schedule.

        Args:
            secret_key: Secret key to rotate.
            hour: Hour of day (0-23).
            minute: Minute of hour (0-59).
            policy: Rotation policy.

        Returns:
            Created ScheduleEntry.
        """
        entry = self.add_schedule(
            secret_key=secret_key,
            schedule_type=ScheduleType.DAILY,
            interval_seconds=86400,
            policy=policy,
        )

        # Set next run to today at specified time
        now = datetime.utcnow()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        entry.next_run_at = next_run

        return entry

    def add_weekly_schedule(
        self,
        secret_key: str,
        day_of_week: int = 0,
        hour: int = 2,
        policy: Optional[RotationPolicy] = None,
    ) -> ScheduleEntry:
        """
        Add a weekly rotation schedule.

        Args:
            secret_key: Secret key.
            day_of_week: Day of week (0=Monday, 6=Sunday).
            hour: Hour of day.
            policy: Rotation policy.

        Returns:
            Created ScheduleEntry.
        """
        entry = self.add_schedule(
            secret_key=secret_key,
            schedule_type=ScheduleType.WEEKLY,
            interval_seconds=604800,
            policy=policy,
        )

        # Calculate next run
        now = datetime.utcnow()
        days_ahead = day_of_week - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_run = now + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=0, second=0, microsecond=0)
        entry.next_run_at = next_run

        return entry

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID."""
        return self._schedules.pop(schedule_id, None) is not None

    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule."""
        entry = self._schedules.get(schedule_id)
        if entry:
            entry.enabled = True
            return True
        return False

    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule."""
        entry = self._schedules.get(schedule_id)
        if entry:
            entry.enabled = False
            return True
        return False

    def get_schedule(self, schedule_id: str) -> Optional[ScheduleEntry]:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    def list_schedules(
        self,
        enabled_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List all schedules."""
        schedules = list(self._schedules.values())
        if enabled_only:
            schedules = [s for s in schedules if s.enabled]
        return [s.to_dict() for s in schedules]

    def get_due_schedules(self) -> List[ScheduleEntry]:
        """Get all schedules that are due for execution."""
        now = datetime.utcnow()
        return [s for s in self._schedules.values() if s.is_due(now)]

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return

        self._running = True
        logger.info("Rotation scheduler started")

        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Rotation scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

            await asyncio.sleep(self._check_interval)

    async def _check_and_execute(self) -> None:
        """Check schedules and execute due ones."""
        due = self.get_due_schedules()

        for schedule in due:
            try:
                result = await self._execute_schedule(schedule)
                if result:
                    schedule.failure_count = 0
                else:
                    schedule.failure_count += 1
                    if schedule.failure_count >= self.MAX_FAILURES:
                        logger.error(
                            "Schedule %s exceeded max failures, disabling",
                            schedule.schedule_id,
                        )
                        schedule.enabled = False
            except Exception as e:
                logger.error(
                    "Schedule execution error for %s: %s",
                    schedule.secret_key, e,
                )
                schedule.failure_count += 1

            # Calculate next run
            schedule.last_run_at = datetime.utcnow()
            schedule.next_run_at = schedule.calculate_next_run()
            schedule.run_count += 1

    async def _execute_schedule(
        self,
        schedule: ScheduleEntry,
    ) -> bool:
        """
        Execute a single schedule.

        Args:
            schedule: Schedule to execute.

        Returns:
            True if execution succeeded.
        """
        if self._on_schedule:
            try:
                result = self._on_schedule(schedule)
                if asyncio.iscoroutine(result):
                    result = await result
                return bool(result)
            except Exception as e:
                logger.error("Schedule callback error: %s", e)
                return False

        if self._execute_fn:
            try:
                result = self._execute_fn(schedule.secret_key)
                if asyncio.iscoroutine(result):
                    result = await result
                return bool(result)
            except Exception as e:
                logger.error("Execute function error: %s", e)
                return False

        logger.warning(
            "No execute function configured for schedule %s",
            schedule.schedule_id,
        )
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total = len(self._schedules)
        enabled = sum(1 for s in self._schedules.values() if s.enabled)
        due = len(self.get_due_schedules())
        total_runs = sum(s.run_count for s in self._schedules.values())
        total_failures = sum(s.failure_count for s in self._schedules.values())

        return {
            "total_schedules": total,
            "enabled_schedules": enabled,
            "due_schedules": due,
            "total_runs": total_runs,
            "total_failures": total_failures,
            "is_running": self._running,
            "check_interval_seconds": self._check_interval,
        }
