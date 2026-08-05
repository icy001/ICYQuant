"""Circuit-breaker-based filtering for service discovery.

Provides ``CircuitFilter`` which removes instances that are in
an open circuit-breaker state, preventing cascading failures
while allowing recovery through half-open retries.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)

CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"


class CircuitFilter:
    """Filters instances using circuit-breaker state.

    Instances with a circuit in OPEN state are removed from
    the candidate pool. After the recovery timeout, circuits
    transition to HALF_OPEN and allow a single probe request.

    Usage::

        cf = CircuitFilter(failure_threshold=5, recovery_timeout=30.0)
        filtered = cf.filter(instances, context)
        cf.record_failure(instance_id)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._lock = threading.RLock()
        self._failure_threshold = int(failure_threshold)
        self._recovery_timeout = float(recovery_timeout)
        self._states: Dict[str, Dict[str, Any]] = {}
        self._filter_count = 0
        self._removed_count = 0
        self._state_counts: Dict[str, int] = {
            CLOSED: 0,
            OPEN: 0,
            HALF_OPEN: 0,
        }

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Remove instances with open circuit breakers.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of instances with closed or
            half-open circuits.
        """
        if not instances:
            return []

        with self._lock:
            self._filter_count += 1

        result: List[ServiceInstance] = []
        removed = 0

        for instance in instances:
            state = self._get_or_init_state(instance.instance_id)
            circuit_state = self._evaluate_state(state)

            if circuit_state == OPEN:
                removed += 1
                continue
            result.append(instance)

        with self._lock:
            self._removed_count += removed

        if removed > 0:
            logger.debug(
                "Circuit filter removed %d of %d instances (open circuits).",
                removed,
                len(instances),
            )

        return result

    def record_success(self, instance_id: str) -> None:
        """Record a successful request to an instance.

        Closes the circuit and resets the failure count.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            state = self._get_or_init_state(instance_id)
            state["failures"] = 0
            state["state"] = CLOSED
            state["last_failure"] = 0.0
            state["last_success"] = time.time()
            self._state_counts[CLOSED] = (
                self._state_counts.get(CLOSED, 0) + 1
            )
            logger.debug(
                "Circuit closed for instance '%s'.", instance_id
            )

    def record_failure(self, instance_id: str) -> None:
        """Record a failed request to an instance.

        Opens the circuit when the failure threshold is reached.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            state = self._get_or_init_state(instance_id)
            state["failures"] += 1
            state["last_failure"] = time.time()

            if state["failures"] >= self._failure_threshold:
                state["state"] = OPEN
                self._state_counts[OPEN] = (
                    self._state_counts.get(OPEN, 0) + 1
                )
                logger.warning(
                    "Circuit opened for instance '%s' after %d failures.",
                    instance_id,
                    state["failures"],
                )

    def get_circuit_state(self, instance_id: str) -> str:
        """Get the circuit-breaker state for an instance.

        Args:
            instance_id: The instance identifier.

        Returns:
            One of ``CLOSED``, ``OPEN``, or ``HALF_OPEN``.
        """
        with self._lock:
            state = self._states.get(instance_id)
            if state is None:
                return CLOSED
            return self._evaluate_state(state)

    def _get_or_init_state(self, instance_id: str) -> Dict[str, Any]:
        state = self._states.get(instance_id)
        if state is None:
            state = {
                "state": CLOSED,
                "failures": 0,
                "last_failure": 0.0,
                "last_success": 0.0,
            }
            self._states[instance_id] = state
        return state

    def _evaluate_state(self, state: Dict[str, Any]) -> str:
        current = state["state"]
        if current == OPEN:
            now = time.time()
            if now - state["last_failure"] >= self._recovery_timeout:
                state["state"] = HALF_OPEN
                self._state_counts[HALF_OPEN] = (
                    self._state_counts.get(HALF_OPEN, 0) + 1
                )
                logger.debug("Circuit half-opened for an instance.")
                return HALF_OPEN
            return OPEN
        return current

    def get_stats(self) -> Dict[str, Any]:
        """Return circuit filter statistics.

        Returns:
            A dictionary with filter counts and per-state
            circuit information.
        """
        with self._lock:
            state_summary: Dict[str, int] = {
                CLOSED: 0,
                OPEN: 0,
                HALF_OPEN: 0,
            }
            for state in self._states.values():
                evaluated = self._evaluate_state(state)
                state_summary[evaluated] = (
                    state_summary.get(evaluated, 0) + 1
                )

            return {
                "filter": "CircuitFilter",
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "filter_count": self._filter_count,
                "removed_count": self._removed_count,
                "tracked_instances": len(self._states),
                "state_summary": state_summary,
                "state_counts": dict(self._state_counts),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CircuitFilter(instances={len(self._states)}, "
                f"threshold={self._failure_threshold})"
            )