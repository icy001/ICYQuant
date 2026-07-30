"""Rebalance Scheduler — manages scheduled and threshold-based rebalance triggers."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    THRESHOLD = "threshold"
    CUSTOM = "custom"
    MANUAL = "manual"


class ScheduleStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ScheduleConfig:
    """Configuration for rebalance scheduling."""

    schedule_type: ScheduleType = ScheduleType.MONTHLY
    day_of_week: int = 1  # Monday=0, Sunday=6 (for WEEKLY)
    day_of_month: int = 1  # 1-28 (for MONTHLY)
    hour_of_day: int = 9
    minute_of_hour: int = 30
    timezone: str = "Asia/Shanghai"
    drift_threshold_pct: float = 5.0  # trigger rebalance if weight drift > 5%
    risk_threshold_pct: float = 10.0  # trigger if risk budget exceeded by 10%
    max_delay_minutes: int = 60
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleTrigger:
    """A trigger condition that initiates rebalance."""

    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trigger_type: str = ""  # calendar | drift | risk | custom
    condition: str = ""
    threshold: float = 0.0
    current_value: float = 0.0
    triggered: bool = False
    last_triggered_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduledTask:
    """A scheduled rebalance task."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    schedule_config: ScheduleConfig = field(default_factory=ScheduleConfig)
    status: ScheduleStatus = ScheduleStatus.PENDING
    next_run_at: float = 0.0
    last_run_at: float = 0.0
    run_count: int = 0
    error_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    triggers: List[ScheduleTrigger] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_due(self) -> bool:
        return self.next_run_at > 0 and time.time() >= self.next_run_at

    @property
    def success_rate(self) -> float:
        total = self.run_count + self.error_count
        return (self.run_count / total * 100) if total > 0 else 100.0


class RebalanceScheduler:
    """Scheduler for managing rebalance timing and triggers.

    Supports calendar-based schedules, threshold-based triggers,
    and custom trigger conditions.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._tasks: Dict[str, ScheduledTask] = {}
        self._handlers: Dict[str, Callable] = {}
        self._execution_log: List[Dict[str, Any]] = []

    def create_schedule(
        self,
        portfolio_id: str,
        config: Optional[ScheduleConfig] = None,
        triggers: Optional[List[ScheduleTrigger]] = None,
    ) -> ScheduledTask:
        task = ScheduledTask(
            portfolio_id=portfolio_id,
            schedule_config=config or ScheduleConfig(),
            triggers=triggers or [],
            status=ScheduleStatus.ACTIVE,
        )
        task.next_run_at = self._compute_next_run(task.schedule_config)
        self._tasks[task.task_id] = task
        logger.info(
            "Created schedule %s for portfolio %s, next run: %s",
            task.task_id, portfolio_id, task.next_run_at,
        )
        return task

    def get_schedule(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def get_schedules_for_portfolio(self, portfolio_id: str) -> List[ScheduledTask]:
        return [t for t in self._tasks.values() if t.portfolio_id == portfolio_id]

    def list_schedules(
        self, status: Optional[ScheduleStatus] = None
    ) -> List[ScheduledTask]:
        results = list(self._tasks.values())
        if status:
            results = [t for t in results if t.status == status]
        return results

    def cancel_schedule(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status in (ScheduleStatus.PENDING, ScheduleStatus.ACTIVE):
            task.status = ScheduleStatus.CANCELLED
            task.updated_at = time.time()
            return True
        return False

    def delete_schedule(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def register_handler(self, trigger_type: str, handler: Callable) -> None:
        """Register a handler function for a trigger type."""
        self._handlers[trigger_type] = handler

    def check_triggers(self, portfolio_id: str) -> List[ScheduleTrigger]:
        """Evaluate all triggers for a portfolio and return triggered ones."""
        triggered: List[ScheduleTrigger] = []
        tasks = self.get_schedules_for_portfolio(portfolio_id)
        for task in tasks:
            for trigger in task.triggers:
                handler = self._handlers.get(trigger.trigger_type)
                if handler:
                    trigger.triggered = handler(trigger, task)
                    if trigger.triggered:
                        trigger.last_triggered_at = time.time()
                        triggered.append(trigger)
        return triggered

    def get_due_tasks(self) -> List[ScheduledTask]:
        """Return all tasks that are due for execution."""
        now = time.time()
        due = []
        for task in self._tasks.values():
            if task.status == ScheduleStatus.ACTIVE and task.next_run_at <= now:
                due.append(task)
        return due

    def execute_task(self, task_id: str) -> bool:
        """Mark task as executed and schedule next run."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.last_run_at = time.time()
        task.run_count += 1
        task.next_run_at = self._compute_next_run(task.schedule_config)
        task.updated_at = time.time()
        self._execution_log.append({
            "task_id": task_id,
            "portfolio_id": task.portfolio_id,
            "executed_at": task.last_run_at,
            "next_run_at": task.next_run_at,
        })
        logger.info("Executed task %s, next run at %s", task_id, task.next_run_at)
        return True

    def record_error(self, task_id: str, error_msg: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.error_count += 1
            task.updated_at = time.time()
            logger.error("Task %s error: %s", task_id, error_msg)

    def _compute_next_run(self, config: ScheduleConfig) -> float:
        """Compute the next run timestamp based on schedule config."""
        import datetime

        now = datetime.datetime.now()
        if config.schedule_type == ScheduleType.DAILY:
            next_run = now.replace(hour=config.hour_of_day, minute=config.minute_of_hour, second=0)
            if next_run <= now:
                next_run += datetime.timedelta(days=1)
        elif config.schedule_type == ScheduleType.WEEKLY:
            days_ahead = config.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now + datetime.timedelta(days=days_ahead)
            next_run = next_run.replace(hour=config.hour_of_day, minute=config.minute_of_hour, second=0)
        elif config.schedule_type == ScheduleType.MONTHLY:
            target_day = min(config.day_of_month, 28)
            if now.day >= target_day:
                if now.month == 12:
                    next_run = now.replace(year=now.year + 1, month=1, day=target_day)
                else:
                    next_run = now.replace(month=now.month + 1, day=target_day)
            else:
                next_run = now.replace(day=target_day)
            next_run = next_run.replace(hour=config.hour_of_day, minute=config.minute_of_hour, second=0)
        elif config.schedule_type == ScheduleType.QUARTERLY:
            current_quarter = (now.month - 1) // 3
            next_quarter = (current_quarter + 1) % 4
            year_add = 1 if next_quarter == 0 else 0
            next_month = next_quarter * 3 + 1
            next_run = now.replace(
                year=now.year + year_add,
                month=next_month,
                day=min(config.day_of_month, 28),
                hour=config.hour_of_day,
                minute=config.minute_of_hour,
                second=0,
            )
        else:
            # Default: next day
            next_run = now + datetime.timedelta(days=1)
            next_run = next_run.replace(hour=config.hour_of_day, minute=config.minute_of_hour, second=0)

        return next_run.timestamp()

    def get_schedule_summary(self) -> Dict[str, Any]:
        tasks = list(self._tasks.values())
        active = sum(1 for t in tasks if t.status == ScheduleStatus.ACTIVE)
        return {
            "total_tasks": len(tasks),
            "active_tasks": active,
            "pending_tasks": sum(1 for t in tasks if t.status == ScheduleStatus.PENDING),
            "completed_runs": sum(t.run_count for t in tasks),
            "total_errors": sum(t.error_count for t in tasks),
        }
