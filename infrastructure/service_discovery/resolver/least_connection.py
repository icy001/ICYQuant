"""Least-connection selection algorithm.

Provides a thread-safe ``LeastConnection`` class that tracks
active connections per instance and selects the one with the
fewest connections.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class LeastConnection:
    """Selects the instance with the fewest active connections.

    Tracks active connections per instance and selects the one
    with the lowest count. Respects ``max_per_instance`` which
    excludes instances at capacity. Thread-safe.

    Args:
        max_per_instance: Maximum connections per instance before
            it is excluded from selection.

    Usage::

        lc = LeastConnection(max_per_instance=1000)
        instance = lc.select(instances)
        lc.acquire(instance.instance_id)
        # ... use instance ...
        lc.release(instance.instance_id)
    """

    def __init__(self, max_per_instance: int = 1000) -> None:
        self._max_per_instance = max_per_instance
        self._lock = threading.RLock()
        self._connections: Dict[str, int] = {}
        self._select_count = 0
        self._total_acquired = 0
        self._total_released = 0

    def acquire(self, instance_id: str) -> None:
        """Mark a connection as acquired for an instance.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            self._connections[instance_id] = (
                self._connections.get(instance_id, 0) + 1
            )
            self._total_acquired += 1

    def release(self, instance_id: str) -> None:
        """Release a connection for an instance.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            current = self._connections.get(instance_id, 0)
            if current > 0:
                self._connections[instance_id] = current - 1
            self._total_released += 1

    def select(
        self, instances: List[ServiceInstance]
    ) -> Optional[ServiceInstance]:
        """Select the instance with the fewest connections.

        Excludes instances that have reached ``max_per_instance``.

        Args:
            instances: Candidate instances.

        Returns:
            The selected instance or None if the list is empty or
            all instances are at capacity.
        """
        if not instances:
            return None
        with self._lock:
            best_instance: Optional[ServiceInstance] = None
            best_count: int = -1
            for instance in instances:
                count = self._connections.get(instance.instance_id, 0)
                if count >= self._max_per_instance:
                    continue
                if best_instance is None or count < best_count:
                    best_instance = instance
                    best_count = count
            if best_instance is not None:
                self._select_count += 1
            return best_instance

    def get_connections(self, instance_id: str) -> int:
        """Get the current connection count for an instance.

        Args:
            instance_id: The instance identifier.

        Returns:
            The number of active connections.
        """
        with self._lock:
            return self._connections.get(instance_id, 0)

    def get_stats(self) -> Dict[str, Any]:
        """Return least-connection statistics.

        Returns:
            A dictionary with connection counts and select stats.
        """
        with self._lock:
            return {
                "selector": "LeastConnection",
                "max_per_instance": self._max_per_instance,
                "active_connections": dict(self._connections),
                "total_active": sum(self._connections.values()),
                "total_acquired": self._total_acquired,
                "total_released": self._total_released,
                "select_count": self._select_count,
            }

    def __repr__(self) -> str:
        total = sum(self._connections.values())
        return f"LeastConnection(active={total}, selects={self._select_count})"