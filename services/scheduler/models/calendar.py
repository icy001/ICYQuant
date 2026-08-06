"""Calendar model — trading calendars, holidays, and market session definitions."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional


class CalendarType(str, enum.Enum):
    """Type of calendar."""

    TRADING = "trading"
    SETTLEMENT = "settlement"
    HOLIDAY = "holiday"
    CUSTOM = "custom"


class CalendarRule(str, enum.Enum):
    """Rule for determining inclusion/exclusion."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    MODIFIED = "modified"


class SessionType(str, enum.Enum):
    """Market session type."""

    PRE_OPEN = "pre_open"
    OPEN_AUCTION = "open_auction"
    CONTINUOUS = "continuous"
    LUNCH_BREAK = "lunch_break"
    CLOSING_AUCTION = "closing_auction"
    AFTER_HOURS = "after_hours"


@dataclass(frozen=True)
class SessionDef:
    """Immutable market session definition."""

    name: str
    session_type: SessionType
    start_time: time
    end_time: time
    allow_trading: bool = True
    description: str = ""


@dataclass(frozen=True)
class CalendarEntry:
    """Immutable calendar entry — a single date with trading rules."""

    date: datetime
    calendar_type: CalendarType = CalendarType.TRADING
    is_trading_day: bool = True
    sessions: List[SessionDef] = field(default_factory=list)
    rule: CalendarRule = CalendarRule.INCLUDE
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def is_in_session(self, reference_time: Optional[datetime] = None) -> bool:
        """Check if the given time falls within a trading session."""
        if not self.is_trading_day:
            return False
        ref = reference_time or datetime.now(timezone.utc)
        ref_time = ref.time()
        for session in self.sessions:
            if session.start_time <= ref_time <= session.end_time and session.allow_trading:
                return True
        return False

    def next_session_start(
        self, reference_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Get the next session start time."""
        if not self.is_trading_day:
            return None
        ref = reference_time or datetime.now(timezone.utc)
        ref_time = ref.time()
        for session in self.sessions:
            if session.start_time > ref_time and session.allow_trading:
                return datetime.combine(ref.date(), session.start_time, tzinfo=ref.tzinfo)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "date": self.date.isoformat() if self.date else None,
            "calendar_type": self.calendar_type.value,
            "is_trading_day": self.is_trading_day,
            "sessions": [
                {
                    "name": s.name,
                    "session_type": s.session_type.value,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat(),
                    "allow_trading": s.allow_trading,
                    "description": s.description,
                }
                for s in self.sessions
            ],
            "rule": self.rule.value,
            "description": self.description,
            "labels": self.labels,
            "tags": self.tags,
        }
