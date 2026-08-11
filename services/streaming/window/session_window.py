"""
Session Window — activity-based windows that group events by periods
of activity separated by gaps of inactivity.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """Result of a window computation."""
    window_start: float
    window_end: float
    event_count: int
    result: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """An active session window."""
    session_key: str
    start_ms: float
    end_ms: float
    events: list[Any] = field(default_factory=list)
    last_event_ms: float = 0.0


class SessionWindow:
    """
    Activity-based windows that group events by session key.

    Sessions are defined by periods of activity separated by
    gaps of inactivity (gap_ms). Each session key has its own
    independent session timeline.

    Usage::

        window = SessionWindow(gap_ms=300000, extract_key=lambda e: e["user_id"])
        window.add_event(event_time, {"user_id": "U1", "action": "click"})
        results = window.get_ready_sessions(current_watermark)
    """

    def __init__(
        self,
        gap_ms: int,
        *,
        extract_key: Optional[Callable[[Any], str]] = None,
        aggregator: Optional[Callable[[list[Any]], Any]] = None,
        max_late_ms: int = 0,
    ) -> None:
        self.gap_ms = gap_ms
        self.extract_key = extract_key or (lambda e: "default")
        self.aggregator = aggregator
        self.max_late_ms = max_late_ms
        self._sessions: dict[str, Session] = {}
        self._completed: list[WindowResult] = []

    def add_event(self, event_time_ms: float, event: Any) -> None:
        """Add an event, creating or merging sessions as needed."""
        key = self.extract_key(event)

        if key in self._sessions:
            session = self._sessions[key]
            gap = event_time_ms - session.end_ms

            if gap <= self.gap_ms:
                # Extend current session
                session.end_ms = event_time_ms
                session.events.append(event)
                session.last_event_ms = event_time_ms
            else:
                # Complete old session, start new one
                self._complete_session(key, session)
                self._sessions[key] = Session(
                    session_key=key,
                    start_ms=event_time_ms,
                    end_ms=event_time_ms,
                    events=[event],
                    last_event_ms=event_time_ms,
                )
        else:
            self._sessions[key] = Session(
                session_key=key,
                start_ms=event_time_ms,
                end_ms=event_time_ms,
                events=[event],
                last_event_ms=event_time_ms,
            )

    def _complete_session(self, key: str, session: Session) -> None:
        """Complete a session and compute its result."""
        if self.aggregator:
            agg_result = self.aggregator(session.events)
        else:
            agg_result = session.events

        result = WindowResult(
            window_start=session.start_ms,
            window_end=session.end_ms,
            event_count=len(session.events),
            result=agg_result,
            metadata={"session_key": key},
        )
        self._completed.append(result)

    def get_ready_sessions(self, watermark_ms: float) -> list[WindowResult]:
        """Get sessions that are ready (gap has passed watermark)."""
        ready = []
        for key, session in list(self._sessions.items()):
            if watermark_ms >= session.end_ms + self.gap_ms + self.max_late_ms:
                self._complete_session(key, session)
                del self._sessions[key]

        results = list(self._completed)
        self._completed.clear()
        return results

    def force_complete_all(self) -> list[WindowResult]:
        """Force complete all active sessions."""
        for key, session in list(self._sessions.items()):
            self._complete_session(key, session)
        self._sessions.clear()

        results = list(self._completed)
        self._completed.clear()
        return results

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)

    @property
    def total_events(self) -> int:
        return sum(len(s.events) for s in self._sessions.values())
