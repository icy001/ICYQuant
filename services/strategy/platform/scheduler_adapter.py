"""
Scheduler Adapter — Connects Strategy Platform to the Distributed Scheduler.

Provides interface for scheduling strategy execution, configuring
cron expressions, and managing scheduled tasks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """Schedule status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduleDefinition:
    """Definition of a scheduled strategy execution."""
    schedule_id: str
    strategy_id: str
    cron_expression: str  # e.g., "0 9 * * 1-5"
    task_type: str = "signal_generation"
    params: dict[str, Any] = field(default_factory=dict)
    timezone: str = "UTC"
    enabled: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3
    timeout_seconds: float = 600.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleExecution:
    """Record of a scheduled execution."""
    execution_id: str
    schedule_id: str
    strategy_id: str
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt: int = 1
    error: Optional[str] = None


class SchedulerAdapter:
    """
    Adapter for the Distributed Scheduler.

    Manages strategy execution schedules, cron-based triggers,
    and scheduled task lifecycle.

    Usage::

        adapter = SchedulerAdapter()
        await adapter.initialize()
        schedule = await adapter.create_schedule(ScheduleDefinition(
            schedule_id="daily_momentum",
            strategy_id="strat_001",
            cron_expression="0 9 * * 1-5",
        ))
    """

    def __init__(self) -> None:
        self._schedules: dict[str, ScheduleDefinition] = {}
        self._executions: dict[str, ScheduleExecution] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the scheduler adapter."""
        self._initialized = True
        logger.info("SchedulerAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("SchedulerAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def create_schedule(self, schedule: ScheduleDefinition) -> ScheduleDefinition:
        """Create a new execution schedule."""
        if schedule.schedule_id in self._schedules:
            raise ValueError(f"Schedule already exists: {schedule.schedule_id}")
        self._schedules[schedule.schedule_id] = schedule
        logger.info(f"Schedule created: {schedule.schedule_id} ({schedule.cron_expression})")
        return schedule

    async def update_schedule(
        self,
        schedule_id: str,
        **kwargs: Any,
    ) -> Optional[ScheduleDefinition]:
        """Update an existing schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        for key, value in kwargs.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        return schedule

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            logger.info(f"Schedule deleted: {schedule_id}")
            return True
        return False

    async def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.enabled = False
        return True

    async def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.enabled = True
        return True

    async def trigger_now(self, schedule_id: str) -> ScheduleExecution:
        """Trigger an immediate execution of a schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule not found: {schedule_id}")

        self._counter += 1
        execution = ScheduleExecution(
            execution_id=f"sched_exec_{self._counter:06d}",
            schedule_id=schedule_id,
            strategy_id=schedule.strategy_id,
        )
        self._executions[execution.execution_id] = execution
        logger.info(f"Schedule triggered: {schedule_id}")
        return execution

    async def get_schedule(self, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    async def list_schedules(
        self,
        strategy_id: Optional[str] = None,
    ) -> list[ScheduleDefinition]:
        """List schedules, optionally filtered by strategy."""
        results = list(self._schedules.values())
        if strategy_id:
            results = [s for s in results if s.strategy_id == strategy_id]
        return results

    async def get_execution(self, execution_id: str) -> Optional[ScheduleExecution]:
        """Get a schedule execution record."""
        return self._executions.get(execution_id)

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_schedules": len([s for s in self._schedules.values() if s.enabled]),
            "total_schedules": len(self._schedules),
        }
