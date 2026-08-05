"""Weighted selection algorithm.

Provides a thread-safe ``Weighted`` class that selects instances
proportional to their weight.
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class Weighted:
    """Selects instances proportional to their weight.

    Uses weighted random selection. Instances with non-positive
    weight are excluded. Supports dynamic weight adjustment
    through instance metadata. Thread-safe.

    Usage::

        wr = Weighted()
        instance = wr.select(instances)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._select_count = 0
        self._weight_sum = 0.0

    def select(
        self, instances: List[ServiceInstance]
    ) -> Optional[ServiceInstance]:
        """Select an instance based on weight.

        Args:
            instances: Candidate instances.

        Returns:
            The selected instance or None if the list is empty.
        """
        if not instances:
            return None
        with self._lock:
            candidates = [i for i in instances if i.weight > 0]
            if not candidates:
                return instances[0]
            weights = [i.weight for i in candidates]
            total = sum(weights)
            if total <= 0:
                return candidates[0]
            self._weight_sum = float(total)
            threshold = random.uniform(0, total)
            cumulative = 0.0
            for instance, weight in zip(candidates, weights):
                cumulative += weight
                if cumulative >= threshold:
                    self._select_count += 1
                    return instance
            self._select_count += 1
            return candidates[-1]

    def get_stats(self) -> Dict[str, Any]:
        """Return weighted selection statistics.

        Returns:
            A dictionary with select count and last weight sum.
        """
        with self._lock:
            return {
                "selector": "Weighted",
                "select_count": self._select_count,
                "last_weight_sum": self._weight_sum,
            }

    def __repr__(self) -> str:
        return f"Weighted(select_count={self._select_count})"