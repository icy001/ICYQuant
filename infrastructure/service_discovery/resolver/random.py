"""Random selection algorithm.

Provides a thread-safe ``Random`` class that selects instances
uniformly at random with optional seed support.
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class Random:
    """Selects an instance uniformly at random.

    Supports optional seeding for reproducible random selection.
    Thread-safe.

    Args:
        seed: Optional seed for the random number generator.

    Usage::

        rnd = Random(seed=42)
        instance = rnd.select(instances)
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self._select_count = 0

    def select(
        self, instances: List[ServiceInstance]
    ) -> Optional[ServiceInstance]:
        """Select an instance uniformly at random.

        Args:
            instances: Candidate instances.

        Returns:
            The selected instance or None if the list is empty.
        """
        if not instances:
            return None
        with self._lock:
            self._select_count += 1
            return self._rng.choice(instances)

    def get_stats(self) -> Dict[str, Any]:
        """Return random selection statistics.

        Returns:
            A dictionary with select count and seed.
        """
        with self._lock:
            return {
                "selector": "Random",
                "seed": self._seed,
                "select_count": self._select_count,
            }

    def __repr__(self) -> str:
        return f"Random(seed={self._seed}, selects={self._select_count})"