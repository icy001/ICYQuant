"""Trigger Factory — convenient creation of trigger instances.

The :class:`TriggerFactory` provides fluent builders for every trigger type,
so callers do not need to import and configure each trigger class directly.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .cron_trigger import CronTrigger
from .interval_trigger import IntervalTrigger
from .calendar_trigger import CalendarTrigger
from .event_trigger import EventTrigger
from .manual_trigger import ManualTrigger
from .webhook_trigger import WebhookTrigger
from .dependency_trigger import DependencyTrigger, DependencyPolicy


class TriggerFactory:
    """Fluent factory for creating trigger instances.

    Usage::

        factory = TriggerFactory()
        cron = factory.cron("*/5 * * * * *", schedule_id="sch-1", job_id="job-1")
        interval = factory.interval(seconds=30, schedule_id="sch-2", job_id="job-2")
    """

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    def cron(
        self,
        expression: str,
        *,
        schedule_id: str = "",
        job_id: str = "",
        timezone: str = "UTC",
        misfire_grace_seconds: int = 60,
        **kwargs: Any,
    ) -> CronTrigger:
        return CronTrigger(
            schedule_id=schedule_id,
            expression=expression,
            timezone=timezone,
            misfire_grace_seconds=misfire_grace_seconds,
            target=job_id,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Interval
    # ------------------------------------------------------------------

    def interval(
        self,
        *,
        schedule_id: str = "",
        job_id: str = "",
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        milliseconds: int = 0,
        jitter: float = 0.0,
        **kwargs: Any,
    ) -> IntervalTrigger:
        return IntervalTrigger(
            schedule_id=schedule_id,
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            milliseconds=milliseconds,
            jitter=jitter,
            target=job_id,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def calendar(
        self,
        *,
        schedule_id: str = "",
        job_id: str = "",
        market: str = "CN",
        session: str = "CONTINUOUS",
        **kwargs: Any,
    ) -> CalendarTrigger:
        return CalendarTrigger(
            schedule_id=schedule_id,
            market=market,
            session=session,
            target=job_id,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Event
    # ------------------------------------------------------------------

    def event(
        self,
        event_type: str,
        *,
        schedule_id: str = "",
        job_id: str = "",
        filter_expr: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EventTrigger:
        return EventTrigger(
            schedule_id=schedule_id,
            event_type=event_type,
            filter_expr=filter_expr or {},
            target=job_id,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Manual
    # ------------------------------------------------------------------

    def manual(
        self,
        *,
        schedule_id: str = "",
        job_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ManualTrigger:
        return ManualTrigger(
            schedule_id=schedule_id,
            target=job_id,
            payload=payload or {},
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    def webhook(
        self,
        *,
        schedule_id: str = "",
        job_id: str = "",
        secret: str = "",
        **kwargs: Any,
    ) -> WebhookTrigger:
        return WebhookTrigger(
            schedule_id=schedule_id,
            target=job_id,
            secret=secret,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Dependency
    # ------------------------------------------------------------------

    def dependency(
        self,
        depends_on: list,
        *,
        schedule_id: str = "",
        job_id: str = "",
        policy: DependencyPolicy = DependencyPolicy.ALL,
        **kwargs: Any,
    ) -> DependencyTrigger:
        return DependencyTrigger(
            schedule_id=schedule_id,
            depends_on=depends_on,
            policy=policy,
            target=job_id,
            **kwargs,
        )
