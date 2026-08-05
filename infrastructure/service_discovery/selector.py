"""Instance selection strategies.

Provides ``ServiceSelector`` strategies (round-robin, random,
weighted) and a ``SelectorFactory`` for choosing a healthy service
instance during resolution. All selectors are thread-safe.
"""

from __future__ import annotations

import logging
import random
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .instance import ServiceInstance

logger = logging.getLogger(__name__)


class ServiceSelector(ABC):
    """Abstract base class for service instance selection strategies."""

    @abstractmethod
    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        """Select a single instance from the provided list.

        Args:
            instances: Candidate instances (assumed already filtered).

        Returns:
            The selected instance or None if the list is empty.
        """


class RoundRobinSelector(ServiceSelector):
    """Selects instances in round-robin order.

    Thread-safe; tracks the next index across selections.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._index = 0

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        if not instances:
            return None
        with self._lock:
            if self._index >= len(instances):
                self._index = 0
            selected = instances[self._index]
            self._index = (self._index + 1) % len(instances)
            return selected


class RandomSelector(ServiceSelector):
    """Selects an instance uniformly at random."""

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        if not instances:
            return None
        return random.choice(instances)


class WeightedSelector(ServiceSelector):
    """Selects an instance proportional to its weight.

    Uses weighted random selection. Instances with non-positive
    weight are excluded. Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
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
            threshold = random.uniform(0, total)
            cumulative = 0.0
            for instance, weight in zip(candidates, weights):
                cumulative += weight
                if cumulative >= threshold:
                    return instance
            return candidates[-1]


class SelectorFactory:
    """Factory for creating selector instances by strategy name."""

    _strategies = {
        "round_robin": RoundRobinSelector,
        "random": RandomSelector,
        "weighted": WeightedSelector,
    }

    @staticmethod
    def create(strategy: str = "round_robin") -> ServiceSelector:
        """Create a selector for the given strategy.

        Args:
            strategy: Strategy name. One of ``round_robin``,
                ``random``, or ``weighted``.

        Returns:
            A new ``ServiceSelector`` instance.

        Raises:
            ValueError: If the strategy is unknown.
        """
        strategy = (strategy or "round_robin").lower()
        cls = SelectorFactory._strategies.get(strategy)
        if cls is None:
            raise ValueError(
                f"Unknown selector strategy '{strategy}'. "
                f"Available: {sorted(SelectorFactory._strategies)}"
            )
        return cls()

    @staticmethod
    def available_strategies() -> List[str]:
        """Return the list of available strategy names."""
        return sorted(SelectorFactory._strategies)

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Return summary statistics for the selector factory.

        Returns:
            A dictionary with the available strategies.
        """
        return {
            "available_strategies": SelectorFactory.available_strategies(),
            "default_strategy": "round_robin",
        }
