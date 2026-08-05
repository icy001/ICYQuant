"""Round-robin selection algorithm.

Provides a thread-safe ``RoundRobin`` class that cycles through
a list of service instances.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class RoundRobin:
    """Selects instances in round-robin order.

    Thread-safe with ``threading.RLock``. Tracks the current
    index across calls.

    Usage::

        rr = RoundRobin()
        instance = rr.next(instances)
        rr.reset()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._index = 0
        self._select_count = 0

    def next(
        self, instances: List[ServiceInstance]
    ) -> Optional[ServiceInstance]:
        """Select the next instance in round-robin order.

        Args:
            instances: Candidate instances.

        Returns:
            The selected instance or None if the list is empty.
        """
        if not instances:
            return None
        with self._lock:
            if self._index >= len(instances):
                self._index = 0
            selected = instances[self._index]
            self._index = (self._index + 1) % len(instances)
            self._select_count += 1
            return selected

    def reset(self) -> None:
        """Reset the round-robin index to zero."""
        with self._lock:
            self._index = 0
            self._select_count = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return round-robin statistics.

        Returns:
            A dictionary with the current index and select count.
        """
        with self._lock:
            return {
                "selector": "RoundRobin",
                "current_index": self._index,
                "select_count": self._select_count,
            }

    def __repr__(self) -> str:
        return f"RoundRobin(index={self._index})"