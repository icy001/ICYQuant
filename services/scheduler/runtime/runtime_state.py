"""Runtime State Manager — tracks and validates state transitions.

The :class:`RuntimeStateManager` enforces valid state transitions
and provides a consistent view of the scheduler runtime lifecycle.
"""

from __future__ import annotations

import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RuntimePhase(str, enum.Enum):
    """Scheduler runtime lifecycle phases."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"
    ERROR = "error"


# Valid transition map
_VALID_TRANSITIONS: Dict[RuntimePhase, Set[RuntimePhase]] = {
    RuntimePhase.UNINITIALIZED: {RuntimePhase.INITIALIZING},
    RuntimePhase.INITIALIZING: {RuntimePhase.ACTIVE, RuntimePhase.ERROR},
    RuntimePhase.ACTIVE: {RuntimePhase.PAUSED, RuntimePhase.DEGRADED, RuntimePhase.SHUTTING_DOWN},
    RuntimePhase.PAUSED: {RuntimePhase.ACTIVE, RuntimePhase.SHUTTING_DOWN},
    RuntimePhase.DEGRADED: {RuntimePhase.ACTIVE, RuntimePhase.ERROR, RuntimePhase.SHUTTING_DOWN},
    RuntimePhase.SHUTTING_DOWN: {RuntimePhase.TERMINATED, RuntimePhase.ERROR},
    RuntimePhase.TERMINATED: set(),
    RuntimePhase.ERROR: {RuntimePhase.SHUTTING_DOWN, RuntimePhase.INITIALIZING},
}


class RuntimeStateManager:
    """Manages scheduler runtime lifecycle state with validation.

    Tracks the current phase, transition history, and enforces
    valid state transitions to prevent illegal runtime states.

    Usage::

        manager = RuntimeStateManager()
        manager.transition(RuntimePhase.INITIALIZING)
        manager.transition(RuntimePhase.ACTIVE)
        assert manager.phase == RuntimePhase.ACTIVE
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._phase: RuntimePhase = RuntimePhase.UNINITIALIZED
        self._history: List[Dict[str, Any]] = []
        self._version: int = 0
        self._error_message: Optional[str] = None

    @property
    def phase(self) -> RuntimePhase:
        """Current runtime phase."""
        return self._phase

    @property
    def version(self) -> int:
        """State version (incremented on each transition)."""
        return self._version

    @property
    def error_message(self) -> Optional[str]:
        """Last error message, if any."""
        return self._error_message

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Return a copy of the transition history."""
        return list(self._history)

    def transition(self, target: RuntimePhase, reason: str = "") -> bool:
        """Attempt a phase transition; return False if invalid."""
        with self._lock:
            valid = _VALID_TRANSITIONS.get(self._phase, set())
            if target not in valid:
                logger.warning(
                    "RuntimeStateManager: invalid transition %s → %s (allowed: %s)",
                    self._phase.value, target.value, [p.value for p in valid],
                )
                return False

            prev = self._phase
            self._phase = target
            self._version += 1
            if target == RuntimePhase.ERROR:
                self._error_message = reason or "transitioned to error state"

            entry = {
                "from": prev.value,
                "to": target.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "version": self._version,
            }
            self._history.append(entry)

            logger.info("RuntimeStateManager: %s → %s (v%d)", prev.value, target.value, self._version)
            return True

    def is_active(self) -> bool:
        """Check if the runtime is in an active state."""
        return self._phase == RuntimePhase.ACTIVE

    def is_operational(self) -> bool:
        """Check if the runtime is operational (active, paused, or degraded)."""
        return self._phase in (RuntimePhase.ACTIVE, RuntimePhase.PAUSED, RuntimePhase.DEGRADED)

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for the state manager."""
        return {
            "phase": self._phase.value,
            "version": self._version,
            "error_message": self._error_message,
            "history_count": len(self._history),
            "last_5_transitions": self._history[-5:] if self._history else [],
        }
