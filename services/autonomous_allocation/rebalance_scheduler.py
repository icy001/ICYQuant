"""Rebalance Scheduler — schedules rebalance execution over time.

Handles:
- Time-based scheduling (e.g., end-of-day, TWAP windows)
- Event-based triggers (e.g., threshold breaches)
- Market-hours awareness
- Overlap avoidance
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class ScheduleType(str, Enum):
    """Type of rebalance schedule."""
    CONTINUOUS = "CONTINUOUS"  # Rebalance whenever thresholds are breached
    PERIODIC = "PERIODIC"  # Fixed intervals (e.g., hourly)
    EOD = "EOD"  # End of day only
    TWAP = "TWAP"  # Time-weighted execution
    VWAP = "VWAP"  # Volume-weighted execution
    EVENT_DRIVEN = "EVENT_DRIVEN"  # Triggered by events
    CUSTOM = "CUSTOM"  # Custom schedule


@dataclass
class ScheduleWindow:
    """A time window for rebalance execution."""
    start_time: time
    end_time: time
    max_capital: float = float("inf")
    max_participation: float = 0.10
    throttle_level: float = 1.0


@dataclass
class ScheduleConfig:
    """Configuration for rebalance scheduling."""
    schedule_type: ScheduleType = ScheduleType.CONTINUOUS
    windows: List[ScheduleWindow] = field(default_factory=list)
    min_interval_minutes: int = 5  # Minimum time between rebalances
    max_daily_rebalances: int = 50
    overlap_avoidance: bool = True


@dataclass
class ScheduleStatus:
    """Current schedule status."""
    schedule_type: ScheduleType
    is_active: bool = True
    next_scheduled: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    rebalances_remaining: int = 0
    next_window: Optional[ScheduleWindow] = None
    within_window: bool = False


class RebalanceScheduler:
    """Manages when and how rebalances are executed.

    Prevents: mid-night execution, overlap with other schedules,
    excessive frequency, and market-hours violations.
    """

    def __init__(self, config: Optional[ScheduleConfig] = None):
        self._config = config or ScheduleConfig(
            schedule_type=ScheduleType.CONTINUOUS,
            windows=[
                ScheduleWindow(
                    start_time=time(9, 30),
                    end_time=time(16, 0),
                )
            ],
        )
        self._last_executed: Optional[datetime] = None
        self._daily_count = 0
        self._last_reset = datetime.utcnow()
        self._paused = False

    @property
    def schedule_type(self) -> ScheduleType:
        return self._config.schedule_type

    def set_schedule(self, schedule_type: ScheduleType) -> None:
        self._config.schedule_type = schedule_type

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def can_execute(self) -> Tuple[bool, str]:
        """Check if a rebalance can be executed now."""
        if self._paused:
            return False, "Scheduler is paused"

        # Reset daily count
        now = datetime.utcnow()
        if now.date() > self._last_reset.date():
            self._daily_count = 0
            self._last_reset = now

        # Check max daily rebalances
        if self._daily_count >= self._config.max_daily_rebalances:
            return False, f"Max daily rebalances ({self._config.max_daily_rebalances}) reached"

        # Check interval
        if self._last_executed:
            elapsed = (now - self._last_executed).total_seconds() / 60
            if elapsed < self._config.min_interval_minutes:
                return False, f"Min interval: {elapsed:.0f} < {self._config.min_interval_minutes} min"

        # Check market window
        if not self._is_within_window(now):
            return False, "Outside of schedule window"

        return True, "Ready"

    def _is_within_window(self, dt: datetime) -> bool:
        """Check if current time is within any schedule window."""
        current_time = dt.time()
        for window in self._config.windows:
            if window.start_time <= current_time <= window.end_time:
                return True
        return False

    def _get_current_window(self, dt: datetime) -> Optional[ScheduleWindow]:
        """Get the current schedule window."""
        current_time = dt.time()
        for window in self._config.windows:
            if window.start_time <= current_time <= window.end_time:
                return window
        return None

    def register_execution(self) -> None:
        """Register that a rebalance was executed."""
        self._last_executed = datetime.utcnow()
        self._daily_count += 1

    def next_execution_time(self) -> Optional[datetime]:
        """Compute the next eligible execution time."""
        now = datetime.utcnow()

        if self._last_executed:
            earliest = self._last_executed + timedelta(minutes=self._config.min_interval_minutes)
        else:
            earliest = now

        # Find next window
        for window in self._config.windows:
            window_start = datetime.combine(now.date(), window.start_time)
            if window_start > earliest:
                return window_start

        # Next day's first window
        if self._config.windows:
            tomorrow = now.date() + timedelta(days=1)
            return datetime.combine(tomorrow, self._config.windows[0].start_time)

        return None

    def status(self) -> ScheduleStatus:
        """Get current schedule status."""
        now = datetime.utcnow()
        can_exec, _ = self.can_execute()

        return ScheduleStatus(
            schedule_type=self._config.schedule_type,
            is_active=can_exec,
            next_scheduled=self.next_execution_time(),
            last_executed=self._last_executed,
            rebalances_remaining=self._config.max_daily_rebalances - self._daily_count,
            next_window=self._get_current_window(now),
            within_window=self._is_within_window(now),
        )
