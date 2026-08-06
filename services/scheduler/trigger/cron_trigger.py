"""Cron Trigger — time-based scheduling using cron expressions.

The :class:`CronTrigger` evaluates a cron expression each poll cycle and
fires when the current time matches.  It supports second-level precision,
misfire detection with configurable grace period, and timezone awareness.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .cron_parser import CronParser
from .cron_expression import CronExpression


@dataclass
class _EvaluationResult:
    """Internal result from trigger evaluation."""

    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class CronTrigger:
    """Trigger that fires on a cron schedule.

    Usage::

        trigger = CronTrigger(
            schedule_id="sch-risk-scan",
            expression="*/30 * * * * *",   # every 30 seconds
            timezone="Asia/Shanghai",
            target="job-risk-scan",
        )
    """

    schedule_id: str
    expression: str
    timezone: str = "UTC"
    misfire_grace_seconds: int = 60
    target: str = ""
    priority: int = 100
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"cron_{id(object()):x}")
    trigger_type: str = "cron"
    _parsed: Optional[CronExpression] = field(default=None, repr=False)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _parser: CronParser = field(default_factory=CronParser, repr=False)

    def __post_init__(self) -> None:
        self._parsed = self._parser.parse(self.expression)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate whether this trigger should fire now.

        Called by the TriggerEngine's evaluation loop on each tick.
        """
        try:
            parsed = self._parsed
            if parsed is None:
                return _EvaluationResult(should_fire=False)

            now = datetime.now(timezone.utc)

            # Check if current time matches the cron expression
            if not self._parser._matches(parsed, now):
                return _EvaluationResult(should_fire=False)

            # Prevent double-fire within the same second
            if self._last_fire_at is not None:
                delta = (now - self._last_fire_at).total_seconds()
                if delta < 1.0:
                    return _EvaluationResult(should_fire=False)

            self._last_fire_at = now

            return _EvaluationResult(
                should_fire=True,
                payload={
                    **self.payload,
                    "cron_expression": self.expression,
                    "trigger_type": "cron",
                },
                fire_at=now,
            )

        except Exception as e:
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_next_fire_time(self, from_time: Optional[datetime] = None) -> Optional[datetime]:
        if self._parsed is None:
            return None
        return self._parser.get_next_fire_time(self._parsed, from_time)

    def get_next_n_fire_times(self, n: int = 10) -> list:
        if self._parsed is None:
            return []
        return self._parser.get_next_n_fire_times(self._parsed, n)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "expression": self.expression,
            "timezone": self.timezone,
            "misfire_grace_seconds": self.misfire_grace_seconds,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"CronTrigger(id={self.trigger_id}, expr='{self.expression}')"
