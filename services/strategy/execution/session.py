"""Strategy execution session.

A session describes the trading execution context of a strategy within one
continuous lifecycle::

    START -> Session CREATED -> ACTIVE -> ... -> CLOSING -> CLOSED

Sessions are deliberately NOT positions: when a strategy stops and later
restarts, a NEW session is created while the position (if any) remains the
source of truth for holdings.  Every signal / intent / order produced during
a session belongs to that session, enabling session-level PnL, exposure,
risk and full trade lineage.
"""

from __future__ import annotations

import itertools
import time
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ExecutionSessionState(str, Enum):
    """Lifecycle of an execution session."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


def session_state_value(state: "str | ExecutionSessionState") -> str:
    """Normalise a session state to its plain string form."""
    if isinstance(state, ExecutionSessionState):
        return state.value
    return state


#: Allowed session state transitions.
SESSION_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"ACTIVE", "FAILED", "CLOSED"}),
    "ACTIVE": frozenset({"PAUSED", "CLOSING", "FAILED"}),
    "PAUSED": frozenset({"ACTIVE", "CLOSING", "FAILED"}),
    "CLOSING": frozenset({"CLOSED", "FAILED"}),
    "CLOSED": frozenset(),
    "FAILED": frozenset(),
}


_session_counter = itertools.count(1)


def new_session_id(strategy_id: str, timestamp: Optional[float] = None) -> str:
    """Session id ``SESSION-<strategy>-<date>-<seq>``, unique per lifecycle."""
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_session_counter)
    return f"SESSION-{strategy_id}-{date_part}-{sequence:02d}"


class ExecutionSessionError(RuntimeError):
    """Raised when a session cannot perform the requested transition."""


class StrategyExecutionSession:
    """Lifecycle-scoped trading execution context for one strategy."""

    def __init__(
        self,
        strategy_id: str,
        session_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> None:
        self.strategy_id = strategy_id
        self.session_id = session_id or new_session_id(strategy_id, now)
        #: Virtual clock: lifecycle timestamps default to this reference time
        #: unless a ``now`` is passed explicitly (enables deterministic tests).
        self._clock = now if now is not None else time.time()
        self.created_at = self._clock
        self.activated_at: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.closed_at: Optional[float] = None
        self.failed_reason: Optional[str] = None
        self.intent_count = 0
        self._state = ExecutionSessionState.CREATED

    @property
    def state(self) -> ExecutionSessionState:
        """Current session state."""
        return self._state

    @property
    def state_value(self) -> str:
        """Current session state as a plain string."""
        return self._state.value

    # --- lifecycle --------------------------------------------------------

    def activate(self, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move CREATED (or PAUSED) -> ACTIVE.

        Only an ACTIVE session may create new execution intents.
        """
        self._transition(ExecutionSessionState.ACTIVE)
        if self.activated_at is None:
            self.activated_at = self._reference_time(now)
        self.paused_at = None
        return self

    def pause(self, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move ACTIVE -> PAUSED.  New intents are blocked while paused."""
        self._transition(ExecutionSessionState.PAUSED)
        self.paused_at = self._reference_time(now)
        return self

    def resume(self, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move PAUSED -> ACTIVE (alias of ``activate``)."""
        return self.activate(now)

    def start_closing(self, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move ACTIVE/PAUSED -> CLOSING.  New intents are blocked."""
        del now
        self._transition(ExecutionSessionState.CLOSING)
        return self

    def close(self, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move CLOSING -> CLOSED."""
        self._transition(ExecutionSessionState.CLOSED)
        self.closed_at = self._reference_time(now)
        return self

    def fail(self, reason: str, now: Optional[float] = None) -> "StrategyExecutionSession":
        """Move any non-terminal state -> FAILED (used on kill / errors)."""
        del now
        self._transition(ExecutionSessionState.FAILED)
        self.failed_reason = reason
        return self

    def _reference_time(self, now: Optional[float]) -> float:
        """Prefer the explicit ``now``, falling back to the session clock."""
        return self._clock if now is None else now

    def _transition(self, target: ExecutionSessionState) -> None:
        allowed = SESSION_TRANSITIONS[self._state.value]
        if target.value not in allowed:
            raise ExecutionSessionError(
                "cannot transition session %s from %s to %s"
                % (self.session_id, self._state.value, target.value)
            )
        self._state = target

    # --- intents ----------------------------------------------------------

    def can_create_intent(self) -> bool:
        """Only ACTIVE sessions may create new execution intents."""
        return self._state == ExecutionSessionState.ACTIVE

    def register_intent(self) -> None:
        """Count a persisted intent (only allowed while ACTIVE)."""
        if not self.can_create_intent():
            raise ExecutionSessionError(
                "session %s is %s and cannot register intents"
                % (self.session_id, self._state.value)
            )
        self.intent_count += 1

    # --- audit ------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Audit-ready snapshot of the session."""
        return {
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "state": self._state.value,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "paused_at": self.paused_at,
            "closed_at": self.closed_at,
            "failed_reason": self.failed_reason,
            "intent_count": self.intent_count,
        }
