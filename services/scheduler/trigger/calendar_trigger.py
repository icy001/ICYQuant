"""Calendar Trigger — market-calendar-aware scheduling.

The :class:`CalendarTrigger` fires only during valid trading periods as
defined by the market calendar.  It automatically skips holidays, weekends,
and non-trading hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .market_calendar import MarketCalendar
from .trading_calendar import Market


@dataclass
class _EvaluationResult:
    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class CalendarTrigger:
    """Trigger that fires only during valid trading periods.

    Usage::

        trigger = CalendarTrigger(
            schedule_id="sch-intraday-risk",
            market="CN",
            session="MORNING",
            target="job-intraday-risk",
        )
    """

    schedule_id: str
    market: str = "CN"
    session: str = "CONTINUOUS"
    target: str = ""
    priority: int = 100
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"calendar_{id(object()):x}")
    trigger_type: str = "calendar"
    _calendar: MarketCalendar = field(default_factory=MarketCalendar)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate whether the current time is within a valid trading period."""
        try:
            now = datetime.now(timezone.utc)

            # Check if today is a trading day
            if not self._calendar.is_trading_day(now, self.market):
                return _EvaluationResult(should_fire=False)

            # Check if we are in the specified session
            if not self._calendar.is_in_session(now, self.market, self.session):
                return _EvaluationResult(should_fire=False)

            # Check if we are in a holiday
            if self._calendar.is_holiday(now, self.market):
                return _EvaluationResult(should_fire=False)

            # Prevent double-fire within the same second
            if self._last_fire_at is not None:
                delta = (now - self._last_fire_at).total_seconds()
                if delta < 1.0:
                    return _EvaluationResult(should_fire=False)

            self._last_fire_at = now
            self._fire_count += 1

            return _EvaluationResult(
                should_fire=True,
                payload={
                    **self.payload,
                    "market": self.market,
                    "session": self.session,
                    "trigger_type": "calendar",
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

    def is_trading_time_now(self) -> bool:
        """Check if now is a valid trading time for this trigger."""
        now = datetime.now(timezone.utc)
        return (
            self._calendar.is_trading_day(now, self.market)
            and self._calendar.is_in_session(now, self.market, self.session)
            and not self._calendar.is_holiday(now, self.market)
        )

    def get_next_trading_time(self) -> Optional[datetime]:
        """Return the next valid trading time."""
        return self._calendar.get_next_trading_time(self.market, self.session)

    def get_session_times(self) -> Dict[str, Any]:
        """Return the trading session time windows for today."""
        return self._calendar.get_session_times(self.market, self.session)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "market": self.market,
            "session": self.session,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return (
            f"CalendarTrigger(id={self.trigger_id}, "
            f"market={self.market}, session={self.session})"
        )
