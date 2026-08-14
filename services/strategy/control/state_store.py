"""Strategy state store with compare-and-set transitions.

The lifecycle cannot live only in memory.  ``StrategyStateStore`` persists
the current control state of every strategy and exposes a compare-and-set
``transition`` so two workers competing on the same strategy never produce a
lost update::

    UPDATE strategy SET state = :new
    WHERE strategy_id = :id AND state = :expected;

    affected_rows == 0  ->  state already changed, reject the transition
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

DEFAULT_STATE = "STOPPED"


@runtime_checkable
class StrategyStateStore(Protocol):
    """Persistent control-state storage with CAS transitions."""

    def get(self, strategy_id: str) -> str:  # pragma: no cover
        """Return the current control state of ``strategy_id``."""
        ...

    def transition(
        self,
        strategy_id: str,
        expected_state: str,
        new_state: str,
    ) -> bool:  # pragma: no cover
        """Atomically move ``strategy_id`` from ``expected_state`` to
        ``new_state``.  Return ``False`` when the current state no longer
        matches ``expected_state`` (concurrent modification).
        """
        ...


class InMemoryStrategyStateStore:
    """Thread-safe in-memory implementation of :class:`StrategyStateStore`."""

    def __init__(self, default_state: str = DEFAULT_STATE) -> None:
        self._default_state = default_state
        self._states: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, strategy_id: str) -> str:
        with self._lock:
            return self._states.get(strategy_id, self._default_state)

    def set(self, strategy_id: str, state: str) -> None:
        """Force ``strategy_id`` into ``state`` (test/setup helper)."""
        with self._lock:
            self._states[strategy_id] = state

    def transition(
        self,
        strategy_id: str,
        expected_state: str,
        new_state: str,
    ) -> bool:
        with self._lock:
            current = self._states.get(strategy_id, self._default_state)
            if current != expected_state:
                return False
            self._states[strategy_id] = new_state
            return True
