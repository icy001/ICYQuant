"""
Production strategy scheduler.

Schedules strategy execution based on time-based rules (cron),
market session events, trigger conditions, and manual invocation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Types of strategy scheduling."""

    CRON = "cron"
    """Cron-based time schedule."""

    MARKET_SESSION = "market_session"
    """Market session based (open, close, intraday)."""

    EVENT_TRIGGER = "event_trigger"
    """Triggered by external events."""

    MANUAL = "manual"
    """Manually triggered only."""

    CONTINUOUS = "continuous"
    """Run continuously (streaming/real-time)."""


class MarketSessionTrigger(str, Enum):
    """Market session trigger points."""

    PRE_MARKET = "pre_market"
    MARKET_OPEN = "market_open"
    MORNING_CLOSE = "morning_close"
    AFTERNOON_OPEN = "afternoon_open"
    MARKET_CLOSE = "market_close"
    AFTER_HOURS = "after_hours"
    EVERY_MINUTE = "every_minute"
    EVERY_5_MINUTES = "every_5_minutes"
    EVERY_15_MINUTES = "every_15_minutes"
    EVERY_HOUR = "every_hour"


@dataclass
class ScheduleConfig:
    """Configuration for a strategy schedule."""

    schedule_type: ScheduleType = ScheduleType.MANUAL

    # Cron settings
    cron_expression: str = ""
    """Standard cron expression (e.g. 0 9 * * 1-5)."""

    # Market session settings
    market_triggers: List[MarketSessionTrigger] = field(default_factory=list)

    # Event trigger settings
    event_types: List[str] = field(default_factory=list)
    """Event type names that trigger this strategy."""

    # General settings
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    max_concurrent_runs: int = 1
    min_interval_seconds: int = 0
    """Minimum interval between runs (anti-flood)."""

    timeout_seconds: int = 300
    retry_on_failure: bool = False
    max_retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_type": self.schedule_type.value,
            "cron_expression": self.cron_expression,
            "market_triggers": [t.value for t in self.market_triggers],
            "event_types": self.event_types,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "max_concurrent_runs": self.max_concurrent_runs,
            "min_interval_seconds": self.min_interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
        }


@dataclass
class ScheduledRun:
    """A scheduled strategy run record."""

    run_id: str
    strategy_id: str
    schedule_type: ScheduleType
    trigger: str
    """What triggered this run (cron expression, event name, etc.)."""

    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "schedule_type": self.schedule_type.value,
            "trigger": self.trigger,
            "scheduled_at": self.scheduled_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": self.result,
        }


class StrategyScheduler:
    """Scheduler for strategy execution timing.

    Manages when strategies should execute, including:
        - Cron-based periodic scheduling
        - Market session aligned scheduling
        - Event-driven triggering
        - Manual execution
    """

    def __init__(self) -> None:
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._run_history: Dict[str, List[ScheduledRun]] = {}
        self._max_history_per_strategy: int = 1000

        self._event_handlers: Dict[str, List[Callable]] = {}
        self._strategy_handlers: Dict[str, List[Callable]] = {}

        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyScheduler initialized")

    async def shutdown(self) -> None:
        self._schedules.clear()
        self._run_history.clear()
        self._event_handlers.clear()
        self._strategy_handlers.clear()
        self._initialized = False
        logger.info("StrategyScheduler shut down")

    # ── Schedule Management ──

    def set_schedule(
        self,
        strategy_id: str,
        config: ScheduleConfig,
    ) -> None:
        """Set or update the schedule for a strategy."""
        self._schedules[strategy_id] = config
        logger.info(
            "Schedule set for %s: type=%s, enabled=%s",
            strategy_id,
            config.schedule_type.value,
            config.enabled,
        )

    def get_schedule(self, strategy_id: str) -> Optional[ScheduleConfig]:
        return self._schedules.get(strategy_id)

    def remove_schedule(self, strategy_id: str) -> None:
        self._schedules.pop(strategy_id, None)
        logger.info("Schedule removed for %s", strategy_id)

    def enable(self, strategy_id: str) -> None:
        schedule = self._schedules.get(strategy_id)
        if schedule:
            schedule.enabled = True

    def disable(self, strategy_id: str) -> None:
        schedule = self._schedules.get(strategy_id)
        if schedule:
            schedule.enabled = False

    def is_enabled(self, strategy_id: str) -> bool:
        schedule = self._schedules.get(strategy_id)
        return schedule is not None and schedule.enabled

    # ── Execution Triggers ──

    async def trigger_manual(
        self,
        strategy_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScheduledRun]:
        """Manually trigger a strategy execution."""
        schedule = self._schedules.get(strategy_id)
        if schedule and not schedule.enabled:
            logger.warning("Schedule disabled for %s, cannot trigger", strategy_id)
            return None

        return await self._create_run(
            strategy_id=strategy_id,
            schedule_type=ScheduleType.MANUAL,
            trigger="manual",
            metadata=metadata,
        )

    async def trigger_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> List[ScheduledRun]:
        """Trigger strategies subscribed to a specific event type."""
        runs: List[ScheduledRun] = []
        for strategy_id, schedule in self._schedules.items():
            if not schedule.enabled:
                continue
            if schedule.schedule_type != ScheduleType.EVENT_TRIGGER:
                continue
            if event_type not in schedule.event_types:
                continue

            run = await self._create_run(
                strategy_id=strategy_id,
                schedule_type=ScheduleType.EVENT_TRIGGER,
                trigger=event_type,
                metadata={"event_data": event_data},
            )
            if run:
                runs.append(run)

        return runs

    async def trigger_market_session(
        self,
        trigger: MarketSessionTrigger,
        session_data: Optional[Dict[str, Any]] = None,
    ) -> List[ScheduledRun]:
        """Trigger strategies aligned to a market session event."""
        runs: List[ScheduledRun] = []
        for strategy_id, schedule in self._schedules.items():
            if not schedule.enabled:
                continue
            if schedule.schedule_type != ScheduleType.MARKET_SESSION:
                continue
            if trigger not in schedule.market_triggers:
                continue

            run = await self._create_run(
                strategy_id=strategy_id,
                schedule_type=ScheduleType.MARKET_SESSION,
                trigger=trigger.value,
                metadata={"session_data": session_data or {}},
            )
            if run:
                runs.append(run)

        return runs

    # ── Handler Registration ──

    def on_run(
        self,
        strategy_id: str,
        handler: Callable,
    ) -> None:
        """Register a handler for strategy execution."""
        self._strategy_handlers.setdefault(strategy_id, []).append(handler)

    def remove_handler(
        self,
        strategy_id: str,
        handler: Callable,
    ) -> None:
        handlers = self._strategy_handlers.get(strategy_id, [])
        if handler in handlers:
            handlers.remove(handler)

    # ── Internals ──

    async def _create_run(
        self,
        strategy_id: str,
        schedule_type: ScheduleType,
        trigger: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScheduledRun]:
        """Create and notify a scheduled run."""
        import uuid

        run = ScheduledRun(
            run_id=uuid.uuid4().hex[:12],
            strategy_id=strategy_id,
            schedule_type=schedule_type,
            trigger=trigger,
            result=metadata or {},
        )

        # Store run
        self._run_history.setdefault(strategy_id, []).append(run)
        history = self._run_history[strategy_id]
        if len(history) > self._max_history_per_strategy:
            self._run_history[strategy_id] = history[-self._max_history_per_strategy:]

        # Notify handlers
        handlers = self._strategy_handlers.get(strategy_id, [])
        for handler in handlers:
            try:
                await handler(run)
            except Exception as e:
                logger.error(
                    "Handler error for strategy %s run %s: %s",
                    strategy_id,
                    run.run_id,
                    e,
                )

        logger.info(
            "Run created: %s for %s [%s/%s]",
            run.run_id,
            strategy_id,
            schedule_type.value,
            trigger,
        )
        return run

    # ── Listing ──

    def list_schedules(self) -> List[Dict[str, Any]]:
        return [
            {"strategy_id": sid, **cfg.to_dict()}
            for sid, cfg in self._schedules.items()
        ]

    def get_run_history(
        self,
        strategy_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        history = self._run_history.get(strategy_id, [])
        return [r.to_dict() for r in history[-limit:]]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schedules": len(self._schedules),
            "enabled_schedules": sum(
                1 for c in self._schedules.values() if c.enabled
            ),
            "total_runs": sum(len(h) for h in self._run_history.values()),
            "initialized": self._initialized,
        }
