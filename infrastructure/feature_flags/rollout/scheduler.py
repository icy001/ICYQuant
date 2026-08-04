"""
Rollout scheduler.

Manages scheduled rollout triggers for
progressive deployment with support for:
    - Immediate execution
    - Daily schedule
    - Weekly schedule
    - Cron-like expressions
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Schedule frequency constants
FREQUENCY_IMMEDIATE = "immediate"
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_CRON = "cron"


class ScheduleConfig:
    """
    Configuration for a scheduled rollout.

    Supports multiple scheduling patterns from
    immediate to cron-like expressions.

    Attributes:
        frequency: Schedule frequency.
        time: Time of day for daily/weekly (HH:MM format).
        weekday: Day of week for weekly (0=Monday, 6=Sunday).
        cron_expression: Cron expression for custom schedules.
        delay_seconds: Delay before first execution.
        max_runs: Maximum number of runs (0 = unlimited).
    """

    def __init__(
        self,
        frequency: str = FREQUENCY_IMMEDIATE,
        time: str = "00:00",
        weekday: int = 0,
        cron_expression: str = "",
        delay_seconds: float = 0.0,
        max_runs: int = 0,
    ) -> None:
        """
        Initialize schedule configuration.

        Args:
            frequency: Schedule frequency.
            time: Time of day in HH:MM format.
            weekday: Day of week (0=Monday, 6=Sunday).
            cron_expression: Cron expression.
            delay_seconds: Initial delay.
            max_runs: Max executions.
        """
        self.frequency = frequency
        self.time = time
        self.weekday = weekday
        self.cron_expression = cron_expression
        self.delay_seconds = delay_seconds
        self.max_runs = max_runs

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "frequency": self.frequency,
            "time": self.time,
            "weekday": self.weekday,
            "cron_expression": self.cron_expression,
            "delay_seconds": self.delay_seconds,
            "max_runs": self.max_runs,
        }


class RolloutScheduler:
    """
    Scheduler for progressive rollout advancement.

    Manages timed advancement of rollout stages
    based on configurable schedules.

    Usage:
        scheduler = RolloutScheduler()
        scheduler.schedule_advance(
            feature_key="new-risk",
            schedule=ScheduleConfig(frequency=FREQUENCY_DAILY, time="02:00"),
        )
        await scheduler.start()
    """

    def __init__(self) -> None:
        """Initialize the rollout scheduler."""
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._run_counts: Dict[str, int] = {}
        self._next_run: Dict[str, float] = {}
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._scheduled_count = 0
        self._executed_count = 0

    def schedule_advance(
        self,
        feature_key: str,
        callback: Callable,
        schedule: ScheduleConfig,
    ) -> None:
        """
        Schedule a rollout advancement.

        Args:
            feature_key: Feature flag key.
            callback: Callback to invoke.
            schedule: Schedule configuration.
        """
        self._schedules[feature_key] = schedule
        self._callbacks[feature_key] = callback
        self._run_counts[feature_key] = 0
        self._next_run[feature_key] = self._compute_next_run(schedule)
        self._scheduled_count += 1

    def unschedule(self, feature_key: str) -> bool:
        """Remove a scheduled advancement."""
        if feature_key in self._schedules:
            del self._schedules[feature_key]
            self._callbacks.pop(feature_key, None)
            self._run_counts.pop(feature_key, None)
            self._next_run.pop(feature_key, None)
            return True
        return False

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._is_running:
            now = time.time()
            to_run = []

            async with self._lock:
                for feature_key, next_time in self._next_run.items():
                    if now >= next_time:
                        schedule = self._schedules.get(feature_key)
                        if schedule:
                            run_count = self._run_counts.get(feature_key, 0)
                            if schedule.max_runs == 0 or run_count < schedule.max_runs:
                                to_run.append(feature_key)
                                self._run_counts[feature_key] = run_count + 1
                                self._next_run[feature_key] = (
                                    self._compute_next_run(schedule, now)
                                )

            for feature_key in to_run:
                callback = self._callbacks.get(feature_key)
                if callback:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(feature_key)
                        else:
                            callback(feature_key)
                        self._executed_count += 1
                    except Exception as e:
                        logger.error(
                            "Scheduled rollout failed for %s: %s",
                            feature_key, e,
                        )

            await asyncio.sleep(1.0)

    def _compute_next_run(
        self,
        schedule: ScheduleConfig,
        after: Optional[float] = None,
    ) -> float:
        """Compute the next run time."""
        now = after or time.time()

        if schedule.delay_seconds > 0 and after is None:
            return now + schedule.delay_seconds

        if schedule.frequency == FREQUENCY_IMMEDIATE:
            return now + schedule.delay_seconds

        elif schedule.frequency == FREQUENCY_DAILY:
            return self._next_daily_run(schedule, now)

        elif schedule.frequency == FREQUENCY_WEEKLY:
            return self._next_weekly_run(schedule, now)

        elif schedule.frequency == FREQUENCY_CRON:
            return self._next_cron_run(schedule, now)

        return now + 60.0  # Default: 1 minute

    def _next_daily_run(
        self,
        schedule: ScheduleConfig,
        now: float,
    ) -> float:
        """Compute next daily run time."""
        dt = datetime.utcfromtimestamp(now)
        hour, minute = self._parse_time(schedule.time)
        next_run = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run.timestamp() <= now:
            next_run += timedelta(days=1)
        return next_run.timestamp()

    def _next_weekly_run(
        self,
        schedule: ScheduleConfig,
        now: float,
    ) -> float:
        """Compute next weekly run time."""
        dt = datetime.utcfromtimestamp(now)
        hour, minute = self._parse_time(schedule.time)
        target = dt.replace(
            hour=hour, minute=minute, second=0, microsecond=0,
        )
        days_ahead = schedule.weekday - dt.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target += timedelta(days=days_ahead)
        if target.timestamp() <= now:
            target += timedelta(weeks=1)
        return target.timestamp()

    def _next_cron_run(
        self,
        schedule: ScheduleConfig,
        now: float,
    ) -> float:
        """Compute next cron run time."""
        # Simplified cron: supports minute, hour, day-of-month
        expr = schedule.cron_expression
        if not expr:
            return now + 60.0

        parts = expr.split()
        if len(parts) >= 2:
            minute = int(parts[0]) if parts[0] != "*" else 0
            hour = int(parts[1]) if parts[1] != "*" else 0
            dt = datetime.utcfromtimestamp(now)
            target = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target.timestamp() <= now:
                target += timedelta(days=1)
            return target.timestamp()

        return now + 60.0

    def _parse_time(self, time_str: str) -> tuple:
        """Parse HH:MM time string."""
        try:
            parts = time_str.split(":")
            return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return (0, 0)

    def get_schedules(self) -> Dict[str, ScheduleConfig]:
        """Get all scheduled configurations."""
        return dict(self._schedules)

    def get_next_run_time(self, feature_key: str) -> Optional[float]:
        """Get the next scheduled run time for a feature."""
        return self._next_run.get(feature_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "scheduled": self._scheduled_count,
            "executed": self._executed_count,
            "pending": len(self._schedules),
            "is_running": self._is_running,
        }
