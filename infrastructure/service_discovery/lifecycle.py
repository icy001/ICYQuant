"""Service instance lifecycle state machine.

Provides ``ServiceLifecycle`` for tracking service instance status
transitions with a defined state machine and history logging.

State machine:
    CREATED -> REGISTERED -> HEALTHY <-> UNHEALTHY -> DEREGISTERED -> REMOVED
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import ServiceDiscoveryError
from .models import ServiceStatus

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: Dict[ServiceStatus, List[ServiceStatus]] = {
    ServiceStatus.CREATED: [ServiceStatus.REGISTERED],
    ServiceStatus.REGISTERED: [ServiceStatus.HEALTHY, ServiceStatus.UNHEALTHY, ServiceStatus.DEREGISTERED],
    ServiceStatus.HEALTHY: [ServiceStatus.UNHEALTHY, ServiceStatus.DEREGISTERED],
    ServiceStatus.UNHEALTHY: [ServiceStatus.HEALTHY, ServiceStatus.DEREGISTERED],
    ServiceStatus.DEREGISTERED: [ServiceStatus.REMOVED, ServiceStatus.REGISTERED],
    ServiceStatus.REMOVED: [ServiceStatus.CREATED],
}

TERMINAL_STATES = {ServiceStatus.REMOVED}


class ServiceLifecycle:
    """Manages service instance lifecycle state transitions.

    Tracks the current status of each (service, instance) pair and
    records a bounded history of transitions. Thread-safe.
    """

    def __init__(self, max_history: int = 10000) -> None:
        self._lock = threading.RLock()
        self._max_history = int(max_history) if max_history > 0 else 10000
        self._states: Dict[str, ServiceStatus] = {}
        self._history: List[Dict[str, Any]] = []

    def _make_key(self, service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def transition(
        self,
        service_name: str,
        instance_id: str,
        new_status: ServiceStatus,
    ) -> Dict[str, Any]:
        """Transition an instance to a new status.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            new_status: The target status.

        Returns:
            A dictionary describing the transition result.

        Raises:
            ServiceDiscoveryError: If the transition is invalid.
        """
        if not isinstance(new_status, ServiceStatus):
            raise ServiceDiscoveryError(
                f"Invalid status type: {type(new_status).__name__}"
            )
        key = self._make_key(service_name, instance_id)
        timestamp = datetime.utcnow()
        with self._lock:
            current = self._states.get(key, ServiceStatus.CREATED)
            if current == new_status:
                result = {
                    "success": True,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "from": current.value,
                    "to": new_status.value,
                    "timestamp": timestamp.isoformat(),
                    "message": "No change; already in target status.",
                }
                self._append_history(result)
                return result
            if not self._can_transition(current, new_status):
                result = {
                    "success": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "from": current.value,
                    "to": new_status.value,
                    "timestamp": timestamp.isoformat(),
                    "error": (
                        f"Invalid transition: {current.value} -> {new_status.value}"
                    ),
                }
                self._append_history(result)
                logger.warning(
                    "Invalid lifecycle transition for '%s': %s -> %s",
                    key,
                    current.value,
                    new_status.value,
                )
                raise ServiceDiscoveryError(result["error"])

            self._states[key] = new_status
            result = {
                "success": True,
                "service_name": service_name,
                "instance_id": instance_id,
                "from": current.value,
                "to": new_status.value,
                "timestamp": timestamp.isoformat(),
            }
            self._append_history(result)
            logger.info(
                "Lifecycle transition '%s': %s -> %s",
                key,
                current.value,
                new_status.value,
            )
            return result

    def _can_transition(self, current: ServiceStatus, target: ServiceStatus) -> bool:
        if current == target:
            return True
        return target in VALID_TRANSITIONS.get(current, [])

    def get_status(self, service_name: str, instance_id: str) -> ServiceStatus:
        """Return the current status of an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            The current ``ServiceStatus``. Returns ``CREATED`` if the
            instance has not been tracked.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            return self._states.get(key, ServiceStatus.CREATED)

    def get_history(
        self,
        service_name: str,
        instance_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Return transition history.

        Args:
            service_name: The logical service name to filter by.
            instance_id: When provided, filter to this instance only.

        Returns:
            A list of transition records, most recent last.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in self._history:
                if entry.get("service_name") != service_name:
                    continue
                if instance_id is not None and entry.get("instance_id") != instance_id:
                    continue
                results.append(dict(entry))
            return results

    def is_terminal(self, service_name: str, instance_id: str) -> bool:
        """Check whether an instance is in a terminal state.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            True if the instance is in a terminal (REMOVED) state.
        """
        return self.get_status(service_name, instance_id) in TERMINAL_STATES

    def _append_history(self, record: Dict[str, Any]) -> None:
        self._history.append(record)
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the lifecycle manager.

        Returns:
            A dictionary with counts of tracked instances, transitions,
            and a breakdown by status.
        """
        with self._lock:
            status_counts: Dict[str, int] = {}
            for status in self._states.values():
                key = status.value
                status_counts[key] = status_counts.get(key, 0) + 1
            return {
                "tracked_instances": len(self._states),
                "total_transitions": len(self._history),
                "terminal_instances": sum(
                    1 for s in self._states.values() if s in TERMINAL_STATES
                ),
                "by_status": status_counts,
                "max_history": self._max_history,
            }

    def __repr__(self) -> str:
        return (
            f"ServiceLifecycle(tracked={len(self._states)}, "
            f"transitions={len(self._history)})"
        )
