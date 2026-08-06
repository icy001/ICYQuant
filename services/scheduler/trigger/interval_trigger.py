"""Interval Trigger — fixed-interval scheduling.

The :class:`IntervalTrigger` fires at a regular interval (seconds, minutes,
hours, or milliseconds).  It supports optional jitter to avoid thundering
herd problems, and start/end time bounds.

Typical use cases: risk scanning, heartbeat, health checks, AI periodic tasks.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional


@dataclass
class _EvaluationResult:
    """Internal result from trigger evaluation."""

    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class IntervalTrigger:
    """Trigger that fires at a fixed interval.

    Usage::

        trigger = IntervalTrigger(
            schedule_id="sch-heartbeat",
            seconds=30,
            jitter=5.0,           # +/- 5 seconds random jitter
            target="job-heartbeat",
        )
    """

    schedule_id: str
    seconds: int = 0
    minutes: int = 0
    hours: int = 0
    milliseconds: int = 0
    jitter: float = 0.0  # max jitter in seconds
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    target: str = ""
    priority: int = 100
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"interval_{id(object()):x}")
    trigger_type: str = "interval"
    _next_fire_at: Optional[float] = field(default=None, repr=False)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)

    @property
    def _interval_seconds(self) -> float:
        return (
            self.milliseconds / 1000.0
            + self.seconds
            + self.minutes * 60
            + self.hours * 3600
        )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate whether this trigger should fire now."""
        try:
            now = datetime.now(timezone.utc)
            now_ts = now.timestamp()

            # Check bounds
            if self.start_at and now < self.start_at:
                return _EvaluationResult(should_fire=False)
            if self.end_at and now > self.end_at:
                return _EvaluationResult(should_fire=False)

            interval = self._interval_seconds
            if interval <= 0:
                return _EvaluationResult(
                    should_fire=False, error="Interval must be positive"
                )

            # First fire or calculate next
            if self._next_fire_at is None:
                jitter_seconds = random.uniform(-self.jitter, self.jitter) if self.jitter else 0
                self._next_fire_at = now_ts + interval + jitter_seconds
                return _EvaluationResult(should_fire=False)

            if now_ts >= self._next_fire_at:
                self._last_fire_at = now
                self._fire_count += 1
                # Schedule next fire
                jitter_seconds = random.uniform(-self.jitter, self.jitter) if self.jitter else 0
                self._next_fire_at = now_ts + interval + jitter_seconds

                return _EvaluationResult(
                    should_fire=True,
                    payload={
                        **self.payload,
                        "interval_seconds": interval,
                        "fire_count": self._fire_count,
                        "trigger_type": "interval",
                    },
                    fire_at=now,
                )

            return _EvaluationResult(should_fire=False)

        except Exception as e:
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_next_fire_time(self) -> Optional[datetime]:
        if self._next_fire_at is None:
            return None
        return datetime.fromtimestamp(self._next_fire_at, tz=timezone.utc)

    def reset(self) -> None:
        """Reset the interval timer (useful after pause/resume)."""
        self._next_fire_at = None
        self._last_fire_at = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "seconds": self.seconds,
            "minutes": self.minutes,
            "hours": self.hours,
            "milliseconds": self.milliseconds,
            "jitter": self.jitter,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return (
            f"IntervalTrigger(id={self.trigger_id}, "
            f"interval={self._interval_seconds}s)"
        )
