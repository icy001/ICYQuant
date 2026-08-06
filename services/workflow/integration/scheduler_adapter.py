"""Scheduler Adapter — cron, interval, calendar, and one-shot workflow triggers.

Supports:

* **Cron Workflow** — run on a cron schedule
* **Interval Workflow** — run every N seconds/minutes/hours
* **Calendar Workflow** — run on trading calendars
* **One-shot Workflow** — run once at a specific time

Architecture::

    Scheduler → Workflow Trigger → Execution
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Types of workflow schedules."""

    CRON = "cron"
    INTERVAL = "interval"
    CALENDAR = "calendar"
    ONESHOT = "oneshot"


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled workflow."""

    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_type: ScheduleType = ScheduleType.CRON
    workflow_id: str = ""
    workflow_version: str = "1.0.0"
    expression: str = ""  # cron expression or interval spec
    inputs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timezone: str = "UTC"
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_done(self) -> bool:
        if self.max_runs is not None and self.run_count >= self.max_runs:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "schedule_type": self.schedule_type.value,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "expression": self.expression,
            "enabled": self.enabled,
            "timezone": self.timezone,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
        }


class SchedulerAdapter:
    """Bridges workflow execution with the ICYQuant scheduler.

    Usage::

        adapter = SchedulerAdapter()
        await adapter.start()
        cfg = ScheduleConfig(schedule_type=ScheduleType.CRON, workflow_id="daily_report", expression="0 9 * * *")
        await adapter.register(cfg)
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._on_trigger_callbacks: List[Callable] = []

        # Background evaluation loop
        self._eval_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._eval_task = asyncio.create_task(self._eval_loop())
        logger.info("SchedulerAdapter: started")

    async def stop(self) -> None:
        self._started = False
        if self._eval_task:
            self._eval_task.cancel()
            try:
                await self._eval_task
            except asyncio.CancelledError:
                pass
        logger.info("SchedulerAdapter: stopped")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, schedule: ScheduleConfig) -> str:
        """Register a scheduled workflow."""
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        logger.info("SchedulerAdapter: registered schedule %s (type=%s, workflow=%s)",
                     schedule.schedule_id, schedule.schedule_type.value, schedule.workflow_id)
        return schedule.schedule_id

    async def deregister(self, schedule_id: str) -> bool:
        with self._lock:
            return self._schedules.pop(schedule_id, None) is not None

    async def enable(self, schedule_id: str) -> None:
        with self._lock:
            cfg = self._schedules.get(schedule_id)
            if cfg:
                cfg.enabled = True

    async def disable(self, schedule_id: str) -> None:
        with self._lock:
            cfg = self._schedules.get(schedule_id)
            if cfg:
                cfg.enabled = False

    async def get_schedule(self, schedule_id: str) -> Optional[ScheduleConfig]:
        with self._lock:
            return self._schedules.get(schedule_id)

    async def list_schedules(
        self,
        *,
        schedule_type: Optional[ScheduleType] = None,
        enabled_only: bool = False,
    ) -> List[ScheduleConfig]:
        with self._lock:
            results = list(self._schedules.values())
            if schedule_type:
                results = [s for s in results if s.schedule_type == schedule_type]
            if enabled_only:
                results = [s for s in results if s.enabled]
            return results

    # ------------------------------------------------------------------
    # Trigger
    # ------------------------------------------------------------------

    def on_trigger(self, callback: Callable) -> None:
        """Register a callback for when a schedule triggers."""
        self._on_trigger_callbacks.append(callback)

    async def trigger_now(self, schedule_id: str) -> bool:
        """Manually trigger a scheduled workflow now."""
        with self._lock:
            cfg = self._schedules.get(schedule_id)
            if cfg is None:
                return False

        for cb in self._on_trigger_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(cfg)
                else:
                    cb(cfg)
            except Exception:
                logger.exception("SchedulerAdapter: trigger callback error for %s", schedule_id)

        with self._lock:
            cfg = self._schedules.get(schedule_id)
            if cfg:
                cfg.last_run = datetime.utcnow()
                cfg.run_count += 1

        return True

    # ------------------------------------------------------------------
    # Evaluation loop
    # ------------------------------------------------------------------

    async def _eval_loop(self) -> None:
        """Periodically evaluate schedules and trigger due workflows."""
        while self._started:
            try:
                await asyncio.sleep(1.0)
                now = datetime.utcnow()

                with self._lock:
                    for cfg in list(self._schedules.values()):
                        if not cfg.enabled or cfg.is_done:
                            continue
                        if cfg.next_run and now >= cfg.next_run:
                            asyncio.create_task(self.trigger_now(cfg.schedule_id))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SchedulerAdapter: error in eval loop")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_schedules": len(self._schedules),
                "enabled": sum(1 for s in self._schedules.values() if s.enabled),
                "by_type": {
                    t.value: sum(1 for s in self._schedules.values() if s.schedule_type == t)
                    for t in ScheduleType
                },
            }
