"""HA state machine for ICYQuant service discovery HA.

Provides ``HAState`` enum and ``HAStateMachine`` for tracking
HA lifecycle states: HEALTHY -> DEGRADED -> FAILING ->
RECOVERING -> HEALTHY.

Supports restricted transitions and full state history tracking.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAState(Enum):
    """High-availability lifecycle states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    RECOVERING = "recovering"
    ISOLATED = "isolated"


_VALID_TRANSITIONS: Dict[HAState, set[HAState]] = {
    HAState.HEALTHY: {
        HAState.DEGRADED,
        HAState.FAILING,
        HAState.ISOLATED,
    },
    HAState.DEGRADED: {
        HAState.HEALTHY,
        HAState.FAILING,
        HAState.RECOVERING,
    },
    HAState.FAILING: {
        HAState.RECOVERING,
        HAState.ISOLATED,
    },
    HAState.RECOVERING: {
        HAState.HEALTHY,
        HAState.DEGRADED,
        HAState.FAILING,
    },
    HAState.ISOLATED: {
        HAState.RECOVERING,
        HAState.FAILING,
    },
}


class HAStateMachine:
    """Tracks HA lifecycle state with restricted transitions.

    Valid transitions:
        HEALTHY -> DEGRADED, FAILING, ISOLATED
        DEGRADED -> HEALTHY, FAILING, RECOVERING
        FAILING -> RECOVERING, ISOLATED
        RECOVERING -> HEALTHY, DEGRADED, FAILING
        ISOLATED -> RECOVERING, FAILING

    Args:
        initial_state: The starting state. Defaults to HEALTHY.
    """

    def __init__(
        self, initial_state: HAState = HAState.HEALTHY
    ) -> None:
        self._lock = threading.RLock()
        self._current_state: HAState = initial_state
        self._transition_count = 0
        self._denied_count = 0
        self._history: List[Dict[str, Any]] = [
            {
                "from": None,
                "to": initial_state.value,
                "reason": "initial",
                "timestamp": self._now_iso(),
            }
        ]
        self._max_history = 500

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    def transition(
        self, new_state: HAState, reason: str = ""
    ) -> Dict[str, Any]:
        """Attempt a state transition.

        Args:
            new_state: The target HAState.
            reason: Human-readable reason for the transition.

        Returns:
            A dictionary describing the transition result.
        """
        with self._lock:
            if not self.can_transition(new_state):
                self._denied_count += 1
                result: Dict[str, Any] = {
                    "transitioned": False,
                    "from": self._current_state.value,
                    "to": new_state.value,
                    "reason": reason,
                    "error": "invalid_transition",
                    "timestamp": self._now_iso(),
                }
                self._record_history("transition_denied", result)
                logger.warning(
                    "State transition denied: %s -> %s (reason: %s).",
                    self._current_state.value,
                    new_state.value,
                    reason,
                )
                return result

            old_state = self._current_state
            self._current_state = new_state
            self._transition_count += 1

        result = {
            "transitioned": True,
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": self._now_iso(),
        }
        self._record_history("transition", result)
        logger.info(
            "State transitioned: %s -> %s (reason: %s).",
            old_state.value,
            new_state.value,
            reason,
        )
        return result

    def current_state(self) -> HAState:
        """Return the current HA state.

        Returns:
            The current HAState value.
        """
        with self._lock:
            return self._current_state

    def can_transition(self, new_state: HAState) -> bool:
        """Check whether a transition to a state is valid.

        Args:
            new_state: The target HAState.

        Returns:
            True if the transition is allowed.
        """
        with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._current_state, set())
            return new_state in allowed

    def get_history(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Return recent state transition history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            A list of transition dictionaries (most recent first).
        """
        with self._lock:
            history = list(reversed(self._history))
            if limit and limit > 0:
                history = history[:limit]
            return history

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the state machine."""
        with self._lock:
            return {
                "current_state": self._current_state.value,
                "transition_count": self._transition_count,
                "denied_count": self._denied_count,
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAStateMachine(state={self._current_state.value!r}, "
                f"transitions={self._transition_count})"
            )