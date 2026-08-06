"""Session Calendar — intraday trading session definitions.

Each market has distinct trading sessions (pre-market, morning, afternoon,
after-hours, night).  The :class:`SessionCalendar` defines session time
windows and provides helpers to check if a given time falls within a session.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from typing import Any, Dict, List, Optional


class TradingSession(str, enum.Enum):
    """Standard trading session identifiers."""

    PRE_MARKET = "PRE_MARKET"
    MORNING = "MORNING"
    LUNCH_BREAK = "LUNCH_BREAK"
    AFTERNOON = "AFTERNOON"
    AFTER_HOURS = "AFTER_HOURS"
    NIGHT = "NIGHT"
    CONTINUOUS = "CONTINUOUS"  # aggregated morning+afternoon (most common)
    FULL_DAY = "FULL_DAY"      # all sessions


@dataclass
class SessionWindow:
    """A time window with start and end times (UTC)."""

    start: time
    end: time
    label: str = ""

    def contains(self, t: time) -> bool:
        if self.start <= self.end:
            return self.start <= t <= self.end
        # Overnight session (e.g., 21:00 - 03:00)
        return t >= self.start or t <= self.end


@dataclass
class SessionCalendar:
    """Intraday trading session definitions per market.

    Defines time windows for each trading session in each market.
    All times are stored as UTC but can be provided in market-local time.

    Default sessions (approximate, in UTC):

    * CN (Asia/Shanghai, UTC+8):
      - PRE_MARKET:  01:00-01:30 UTC
      - MORNING:     01:30-03:30 UTC
      - AFTERNOON:   05:00-07:00 UTC
      - CONTINUOUS:  01:30-07:00 UTC (aggregated)

    * US (America/New_York, UTC-5/-4):
      - PRE_MARKET:  09:00-14:30 UTC
      - MORNING:     14:30-21:00 UTC
      - AFTER_HOURS: 21:00-01:00 UTC (next day)
    """

    # Default session definitions (UTC times, approximate)
    _DEFAULT_SESSIONS: Dict[str, Dict[str, List[SessionWindow]]] = {
        "CN": {
            TradingSession.PRE_MARKET: [
                SessionWindow(time(1, 0), time(1, 30), "CN Pre-Market")
            ],
            TradingSession.MORNING: [
                SessionWindow(time(1, 30), time(3, 30), "CN Morning")
            ],
            TradingSession.AFTERNOON: [
                SessionWindow(time(5, 0), time(7, 0), "CN Afternoon")
            ],
            TradingSession.CONTINUOUS: [
                SessionWindow(time(1, 30), time(3, 30), "CN Morning"),
                SessionWindow(time(5, 0), time(7, 0), "CN Afternoon"),
            ],
            TradingSession.FULL_DAY: [
                SessionWindow(time(1, 0), time(7, 0), "CN Full Day"),
            ],
        },
        "US": {
            TradingSession.PRE_MARKET: [
                SessionWindow(time(9, 0), time(14, 30), "US Pre-Market")
            ],
            TradingSession.MORNING: [
                SessionWindow(time(14, 30), time(21, 0), "US Regular")
            ],
            TradingSession.AFTER_HOURS: [
                SessionWindow(time(21, 0), time(23, 59), "US After-Hours 1"),
                SessionWindow(time(0, 0), time(1, 0), "US After-Hours 2"),
            ],
            TradingSession.CONTINUOUS: [
                SessionWindow(time(14, 30), time(21, 0), "US Regular"),
            ],
            TradingSession.FULL_DAY: [
                SessionWindow(time(9, 0), time(1, 0), "US Full Day"),
            ],
        },
        "HK": {
            TradingSession.MORNING: [
                SessionWindow(time(1, 30), time(4, 0), "HK Morning")
            ],
            TradingSession.AFTERNOON: [
                SessionWindow(time(5, 0), time(8, 0), "HK Afternoon")
            ],
            TradingSession.CONTINUOUS: [
                SessionWindow(time(1, 30), time(4, 0), "HK Morning"),
                SessionWindow(time(5, 0), time(8, 0), "HK Afternoon"),
            ],
        },
        "CRYPTO": {
            TradingSession.CONTINUOUS: [
                SessionWindow(time(0, 0), time(23, 59, 59), "Crypto 24/7")
            ],
        },
    }

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, List[SessionWindow]]] = {}
        # Deep-copy defaults
        for market, sessions in self._DEFAULT_SESSIONS.items():
            self._sessions[market] = {
                k: [SessionWindow(w.start, w.end, w.label) for w in v]
                for k, v in sessions.items()
            }

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def set_session(
        self,
        market: str,
        session: str,
        windows: List[SessionWindow],
    ) -> None:
        """Override session windows for a market."""
        mkt = market.upper()
        if mkt not in self._sessions:
            self._sessions[mkt] = {}
        self._sessions[mkt][session.upper()] = windows

    def get_session(self, market: str, session: str) -> List[SessionWindow]:
        """Get session windows for a market."""
        mkt = market.upper()
        sess = session.upper()
        return self._sessions.get(mkt, {}).get(sess, [])

    def get_all_sessions(self, market: str) -> Dict[str, List[SessionWindow]]:
        return self._sessions.get(market.upper(), {})

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_in_session(
        self,
        dt: datetime,
        market: str = "CN",
        session: str = "CONTINUOUS",
    ) -> bool:
        """Check if *dt* falls within the given trading session."""
        windows = self.get_session(market, session)
        t = dt.time()
        for window in windows:
            if window.contains(t):
                return True
        return False

    def get_current_session(self, dt: Optional[datetime] = None, market: str = "CN") -> Optional[str]:
        """Return the name of the currently active session, or None."""
        now = dt or datetime.now(timezone.utc)
        t = now.time()
        for session_name, windows in self._sessions.get(market.upper(), {}).items():
            for window in windows:
                if window.contains(t):
                    return session_name
        return None

    def get_next_session_start(
        self, dt: Optional[datetime] = None, market: str = "CN", session: str = "CONTINUOUS"
    ) -> Optional[datetime]:
        """Return the start time of the next occurrence of a session."""
        now = dt or datetime.now(timezone.utc)
        windows = self.get_session(market, session)
        if not windows:
            return None

        # Today's first window
        first_window = windows[0]
        candidate = now.replace(
            hour=first_window.start.hour,
            minute=first_window.start.minute,
            second=first_window.start.second,
            microsecond=0,
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def get_session_times(self, market: str, session: str) -> Dict[str, Any]:
        """Return session time windows as a dict."""
        windows = self.get_session(market, session)
        return {
            "market": market,
            "session": session,
            "windows": [
                {
                    "start": w.start.isoformat(),
                    "end": w.end.isoformat(),
                    "label": w.label,
                }
                for w in windows
            ],
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "markets_configured": list(self._sessions.keys()),
            "sessions_per_market": {
                m: list(s.keys()) for m, s in self._sessions.items()
            },
        }
