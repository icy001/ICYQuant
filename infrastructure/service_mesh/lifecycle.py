"""Lifecycle management for the Service Mesh.

Provides ``MeshLifecycle`` for tracking state transitions:
Created -> Bootstrapped -> Running -> Reloading -> Stopped.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MeshState(str, Enum):
    """Mesh lifecycle states."""

    CREATED = "created"
    BOOTSTRAPPED = "bootstrapped"
    RUNNING = "running"
    RELOADING = "reloading"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


_VALID_TRANSITIONS: Dict[MeshState, List[MeshState]] = {
    MeshState.CREATED: [MeshState.BOOTSTRAPPED, MeshState.FAILED],
    MeshState.BOOTSTRAPPED: [MeshState.RUNNING, MeshState.FAILED],
    MeshState.RUNNING: [
        MeshState.RELOADING,
        MeshState.DRAINING,
        MeshState.STOPPED,
        MeshState.FAILED,
    ],
    MeshState.RELOADING: [MeshState.RUNNING, MeshState.FAILED],
    MeshState.DRAINING: [MeshState.STOPPED, MeshState.FAILED],
    MeshState.STOPPED: [MeshState.CREATED],
    MeshState.FAILED: [MeshState.CREATED],
}


class MeshLifecycle:
    """Manages the lifecycle state of the service mesh."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = MeshState.CREATED
        self._transition_count = 0
        self._transition_history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._listeners: Dict[MeshState, List[Callable]] = {}
        self._state_start_time = time.monotonic()
        self._state_durations: Dict[str, float] = {}

    @property
    def state(self) -> MeshState:
        return self._state

    @property
    def state_value(self) -> str:
        return self._state.value

    @property
    def is_running(self) -> bool:
        return self._state == MeshState.RUNNING

    def can_transition_to(self, target: MeshState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, [])

    def transition_to(
        self,
        target: MeshState,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Transition to a new state."""
        with self._lock:
            if not self.can_transition_to(target):
                return {
                    "success": False,
                    "error": (
                        f"Invalid transition: {self._state.value} -> "
                        f"{target.value}"
                    ),
                    "current_state": self._state.value,
                }

            # Record duration of current state
            now = time.monotonic()
            duration = now - self._state_start_time
            current_state_name = self._state.value
            if current_state_name not in self._state_durations:
                self._state_durations[current_state_name] = 0.0
            self._state_durations[current_state_name] += duration

            # Execute transition
            old_state = self._state
            self._state = target
            self._transition_count += 1
            self._state_start_time = now

            # Record history
            record = {
                "from": old_state.value,
                "to": target.value,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_s": duration,
                "transition_number": self._transition_count,
            }
            self._transition_history.append(record)
            if len(self._transition_history) > self._max_history:
                self._transition_history = self._transition_history[
                    -self._max_history:
                ]

        # Notify listeners (outside lock to avoid deadlocks)
        for listener in self._listeners.get(target, []):
            try:
                listener(old_state, target, record)
            except Exception as exc:
                logger.warning(
                    "Lifecycle listener failed: %s", exc
                )

        logger.info(
            "Mesh transition: %s -> %s (reason: %s)",
            old_state.value,
            target.value,
            reason,
        )

        return {
            "success": True,
            "previous_state": old_state.value,
            "current_state": target.value,
            "transition_number": self._transition_count,
        }

    def on_state(
        self, state: MeshState, listener: Callable
    ) -> None:
        """Register a listener for state transitions to a specific state."""
        if state not in self._listeners:
            self._listeners[state] = []
        self._listeners[state].append(listener)

    def get_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._transition_history[-limit:])

    def get_durations(self) -> Dict[str, float]:
        with self._lock:
            durations = dict(self._state_durations)
            # Add current state's elapsed time
            current_name = self._state.value
            elapsed = time.monotonic() - self._state_start_time
            durations[current_name] = (
                durations.get(current_name, 0.0) + elapsed
            )
            return durations

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_state": self._state.value,
                "transition_count": self._transition_count,
                "history_size": len(self._transition_history),
                "listeners": {
                    k.value: len(v)
                    for k, v in self._listeners.items()
                },
                "state_durations": self.get_durations(),
            }

    def reset(self) -> None:
        with self._lock:
            self._state = MeshState.CREATED
            self._transition_count = 0
            self._transition_history.clear()
            self._state_durations.clear()
            self._state_start_time = time.monotonic()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshLifecycle(state={self._state.value}, "
                f"transitions={self._transition_count})"
            )
