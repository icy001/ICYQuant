from __future__ import annotations

import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List


class RuntimeState(str, Enum):
    """Enumeration of possible lifecycle states for the workflow runtime."""

    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class RuntimeStateManager:
    """Manages the lifecycle state of a workflow runtime with validated transitions.

    The manager enforces a finite state machine over :class:`RuntimeState` values.
    Transitions are only applied when allowed by the transition table; any state may
    transition to ``ERROR``, and ``ERROR`` may only recover to ``IDLE``.
    """

    def __init__(self) -> None:
        self._state: RuntimeState = RuntimeState.IDLE
        self._lock = threading.RLock()
        self._transitions: Dict[RuntimeState, List[RuntimeState]] = self._build_transitions()
        self._state_history: List[Dict[str, Any]] = []
        self._max_history: int = 100
        self._callbacks: List[Callable[[RuntimeState, RuntimeState], None]] = []

    @staticmethod
    def _build_transitions() -> Dict[RuntimeState, List[RuntimeState]]:
        """Build the map of allowed source-state to target-states."""
        return {
            RuntimeState.IDLE: [RuntimeState.INITIALIZING],
            RuntimeState.INITIALIZING: [RuntimeState.READY],
            RuntimeState.READY: [RuntimeState.RUNNING],
            RuntimeState.RUNNING: [RuntimeState.PAUSED, RuntimeState.STOPPING],
            RuntimeState.PAUSED: [RuntimeState.RESUMING, RuntimeState.STOPPING],
            RuntimeState.RESUMING: [RuntimeState.RUNNING],
            RuntimeState.STOPPING: [RuntimeState.STOPPED],
            RuntimeState.STOPPED: [RuntimeState.IDLE],
            RuntimeState.ERROR: [RuntimeState.IDLE],
        }

    def get_state(self) -> RuntimeState:
        """Return the current runtime state."""
        with self._lock:
            return self._state

    def can_transition(self, to: RuntimeState) -> bool:
        """Return True if transitioning from the current state to ``to`` is allowed."""
        with self._lock:
            return self._can_transition_locked(to)

    def _can_transition_locked(self, to: RuntimeState) -> bool:
        """Transition check assuming the caller already holds the lock."""
        if to == RuntimeState.ERROR:
            return True
        allowed = self._transitions.get(self._state, [])
        return to in allowed

    def set_state(self, new_state: RuntimeState) -> bool:
        """Validate and apply a state transition.

        Returns True when the transition was applied (or the state was already equal),
        and False when the transition is not allowed by the state machine.
        """
        with self._lock:
            old_state = self._state
            if new_state == old_state:
                return True
            if not self._can_transition_locked(new_state):
                return False
            self._state = new_state
            self._record_history(old_state, new_state)
        self._notify_callbacks(old_state, new_state)
        return True

    def _record_history(self, old: RuntimeState, new: RuntimeState) -> None:
        """Append a transition record to history, trimming to ``_max_history``."""
        self._state_history.append(
            {
                "from": old,
                "to": new,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if len(self._state_history) > self._max_history:
            self._state_history = self._state_history[-self._max_history:]

    def get_history(self) -> List[Dict[str, Any]]:
        """Return a copy of the recorded state transition history."""
        with self._lock:
            return list(self._state_history)

    def register_transition_callback(
        self, callback: Callable[[RuntimeState, RuntimeState], None]
    ) -> None:
        """Register a callback invoked after each successful state transition."""
        with self._lock:
            self._callbacks.append(callback)

    def _notify_callbacks(self, old: RuntimeState, new: RuntimeState) -> None:
        """Notify all registered callbacks of a state transition.

        Callback exceptions are swallowed so that observer failures can never
        destabilize the state machine.
        """
        with self._lock:
            callbacks = list(self._callbacks)
        for callback in callbacks:
            try:
                callback(old, new)
            except Exception:
                # Observer failures must not affect state transitions.
                pass

    def reset(self) -> None:
        """Reset the manager back to IDLE and clear transition history."""
        with self._lock:
            self._state = RuntimeState.IDLE
            self._state_history.clear()
