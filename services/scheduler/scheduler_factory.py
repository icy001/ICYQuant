"""Scheduler Factory — pre-built schedule templates for common patterns.

The :class:`SchedulerFactory` provides factory methods for creating
commonly used schedule configurations without manual boilerplate.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleType, ScheduleStatus, ScheduleConfig


class SchedulerFactory:
    """Factory for creating common schedule definitions.

    Provides pre-built templates for:
    * Linear pipelines (sequential execution)
    * Fork-Join patterns (parallel branches)
    * Decision trees (conditional branching)

    Usage::

        factory = SchedulerFactory()
        daily_report = factory.cron_schedule(
            name="daily_report",
            cron="0 9 * * 1-5",
            target="wf_report_001",
        )
    """

    @staticmethod
    def cron_schedule(
        name: str,
        cron: str,
        target: str,
        payload: Optional[Dict[str, Any]] = None,
        owner: str = "",
        description: str = "",
    ) -> ScheduleDefinition:
        """Create a cron-based schedule.

        Args:
            name: Human-readable schedule name.
            cron: Cron expression (e.g. "0 9 * * 1-5").
            target: Workflow ID or system task reference.
            payload: Payload passed to each execution.
            owner: Owning team/user.
            description: Description of the schedule.
        """
        schedule_id = f"sch_cron_{uuid.uuid4().hex[:12]}"
        return ScheduleDefinition(
            schedule_id=schedule_id,
            name=name,
            schedule_type=ScheduleType.CRON,
            trigger_expression=cron,
            target=target,
            payload=payload or {},
            config=ScheduleConfig(priority=100),
            status=ScheduleStatus.DRAFT,
            owner=owner,
            description=description,
        )

    @staticmethod
    def interval_schedule(
        name: str,
        interval_seconds: float,
        target: str,
        payload: Optional[Dict[str, Any]] = None,
        owner: str = "",
        description: str = "",
    ) -> ScheduleDefinition:
        """Create an interval-based schedule.

        Args:
            name: Human-readable schedule name.
            interval_seconds: Interval in seconds between triggers.
            target: Workflow ID or system task reference.
            payload: Payload passed to each execution.
            owner: Owning team/user.
            description: Description of the schedule.
        """
        schedule_id = f"sch_interval_{uuid.uuid4().hex[:12]}"
        return ScheduleDefinition(
            schedule_id=schedule_id,
            name=name,
            schedule_type=ScheduleType.INTERVAL,
            trigger_expression=f"PT{interval_seconds}S",
            target=target,
            payload=payload or {},
            config=ScheduleConfig(priority=100),
            status=ScheduleStatus.DRAFT,
            owner=owner,
            description=description,
        )

    @staticmethod
    def oneshot_schedule(
        name: str,
        target: str,
        fire_at: Optional[datetime] = None,
        payload: Optional[Dict[str, Any]] = None,
        owner: str = "",
        description: str = "",
    ) -> ScheduleDefinition:
        """Create a one-shot schedule that fires once.

        Args:
            name: Human-readable schedule name.
            target: Workflow ID or system task reference.
            fire_at: When to fire (None = immediately).
            payload: Payload passed to the execution.
            owner: Owning team/user.
            description: Description of the schedule.
        """
        schedule_id = f"sch_oneshot_{uuid.uuid4().hex[:12]}"
        return ScheduleDefinition(
            schedule_id=schedule_id,
            name=name,
            schedule_type=ScheduleType.ONESHOT,
            trigger_expression=fire_at.isoformat() if fire_at else "now",
            target=target,
            payload=payload or {},
            config=ScheduleConfig(
                overlapping_policy="skip",
                misfire_policy="ignore",
                max_concurrent=1,
            ),
            status=ScheduleStatus.DRAFT,
            owner=owner,
            description=description,
            next_fire_at=fire_at or datetime.now(timezone.utc),
        )

    @staticmethod
    def event_schedule(
        name: str,
        event_key: str,
        target: str,
        payload: Optional[Dict[str, Any]] = None,
        owner: str = "",
        description: str = "",
    ) -> ScheduleDefinition:
        """Create an event-driven schedule.

        Fires when a specific event is published on the EventBus.

        Args:
            name: Human-readable schedule name.
            event_key: EventBus event key to listen for.
            target: Workflow ID or system task reference.
            payload: Payload passed to each execution.
            owner: Owning team/user.
            description: Description of the schedule.
        """
        schedule_id = f"sch_event_{uuid.uuid4().hex[:12]}"
        return ScheduleDefinition(
            schedule_id=schedule_id,
            name=name,
            schedule_type=ScheduleType.EVENT,
            trigger_expression=event_key,
            target=target,
            payload=payload or {},
            config=ScheduleConfig(priority=200),
            status=ScheduleStatus.DRAFT,
            owner=owner,
            description=description,
        )

    @staticmethod
    def calendar_schedule(
        name: str,
        calendar_rule: str,
        target: str,
        payload: Optional[Dict[str, Any]] = None,
        owner: str = "",
        description: str = "",
    ) -> ScheduleDefinition:
        """Create a calendar-based schedule (trading days, holidays, etc.).

        Args:
            name: Human-readable schedule name.
            calendar_rule: Calendar rule expression.
            target: Workflow ID or system task reference.
            payload: Payload passed to each execution.
            owner: Owning team/user.
            description: Description of the schedule.
        """
        schedule_id = f"sch_cal_{uuid.uuid4().hex[:12]}"
        return ScheduleDefinition(
            schedule_id=schedule_id,
            name=name,
            schedule_type=ScheduleType.CALENDAR,
            trigger_expression=calendar_rule,
            target=target,
            payload=payload or {},
            config=ScheduleConfig(priority=100),
            status=ScheduleStatus.DRAFT,
            owner=owner,
            description=description,
        )
