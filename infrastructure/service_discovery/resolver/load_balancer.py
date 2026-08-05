"""Load balancer orchestration.

Provides ``LoadBalancer`` which acts as a central registry for
multiple selection strategies and supports single and multi-instance
selection with fallback strategy resolution.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext
from .selector import (
    ConsistentHashLoadBalancer,
    LeastConnectionLoadBalancer,
    LeastLatencyLoadBalancer,
    LoadBalancerSelector,
    RandomLoadBalancer,
    RoundRobinLoadBalancer,
    WeightedLoadBalancer,
)

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Central load balancer supporting pluggable strategies.

    Provides single and multi-instance selection with automatic
    strategy resolution. Built-in strategies include round_robin,
    random, weighted, least_connection, least_latency, and
    consistent_hash.

    Args:
        default_strategy: The default strategy name to use when
            none is specified.
    """

    def __init__(self, default_strategy: str = "round_robin") -> None:
        self._lock = threading.RLock()
        self._default_strategy = (default_strategy or "round_robin").lower()
        self._strategies: Dict[str, LoadBalancerSelector] = {}
        self._stats: Dict[str, Any] = {
            "total_selects": 0,
            "total_select_many": 0,
            "strategy_usage": {},
        }
        self._register_builtin_strategies()

    def _register_builtin_strategies(self) -> None:
        self._strategies["round_robin"] = RoundRobinLoadBalancer()
        self._strategies["random"] = RandomLoadBalancer()
        self._strategies["weighted"] = WeightedLoadBalancer()
        self._strategies["least_connection"] = LeastConnectionLoadBalancer()
        self._strategies["least_latency"] = LeastLatencyLoadBalancer()
        self._strategies["consistent_hash"] = ConsistentHashLoadBalancer()

    async def select(
        self,
        instances: List[ServiceInstance],
        strategy: Optional[str] = None,
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        """Select a single instance using the specified strategy.

        Args:
            instances: Candidate instances.
            strategy: Strategy name (falls back to default).
            context: Optional resolution context.

        Returns:
            The selected instance or None.
        """
        if not instances:
            return None
        strategy_name = (strategy or self._default_strategy).lower()
        with self._lock:
            selector = self._strategies.get(strategy_name)
            if selector is None:
                logger.warning(
                    "Unknown strategy '%s'; falling back to '%s'.",
                    strategy_name,
                    self._default_strategy,
                )
                selector = self._strategies.get(self._default_strategy)
                if selector is None:
                    return instances[0]
            self._stats["total_selects"] += 1
            usage = self._stats["strategy_usage"]
            usage[strategy_name] = usage.get(strategy_name, 0) + 1
        return await selector.select(instances, context)

    async def select_many(
        self,
        instances: List[ServiceInstance],
        count: int,
        strategy: Optional[str] = None,
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Select multiple instances using the specified strategy.

        Args:
            instances: Candidate instances.
            count: Number of instances to select.
            strategy: Strategy name (falls back to default).
            context: Optional resolution context.

        Returns:
            A list of selected instances.
        """
        if not instances or count <= 0:
            return []
        strategy_name = (strategy or self._default_strategy).lower()
        with self._lock:
            selector = self._strategies.get(strategy_name)
            if selector is None:
                selector = self._strategies.get(self._default_strategy)
                if selector is None:
                    return instances[:count]
            self._stats["total_select_many"] += 1
        selected: List[ServiceInstance] = []
        used_ids: set = set()
        candidates = list(instances)
        for _ in range(count):
            if not candidates:
                break
            candidate = await selector.select(candidates, context)
            if candidate is None:
                break
            selected.append(candidate)
            used_ids.add(candidate.instance_id)
            candidates = [c for c in candidates if c.instance_id not in used_ids]
        return selected

    def register_strategy(
        self, name: str, selector: LoadBalancerSelector
    ) -> None:
        """Register a custom strategy selector.

        Args:
            name: The strategy name.
            selector: The ``LoadBalancerSelector`` instance.
        """
        if not name:
            raise ValueError("Strategy name cannot be empty.")
        if not isinstance(selector, LoadBalancerSelector):
            raise TypeError(
                "selector must be an instance of LoadBalancerSelector."
            )
        with self._lock:
            self._strategies[name.lower()] = selector
            logger.debug("Registered load balancer strategy: %s", name)

    def get_strategy(self, name: str) -> LoadBalancerSelector:
        """Get a registered strategy selector by name.

        Args:
            name: The strategy name.

        Returns:
            The ``LoadBalancerSelector`` instance.

        Raises:
            KeyError: If the strategy is not found.
        """
        with self._lock:
            name = name.lower()
            if name not in self._strategies:
                raise KeyError(
                    f"Strategy '{name}' not registered. "
                    f"Available: {sorted(self._strategies)}"
                )
            return self._strategies[name]

    def get_stats(self) -> Dict[str, Any]:
        """Return load balancer statistics.

        Returns:
            A dictionary with selection counts and per-strategy
            statistics.
        """
        with self._lock:
            strategy_stats: Dict[str, Any] = {}
            for name, selector in self._strategies.items():
                strategy_stats[name] = selector.get_stats()
            total = self._stats["total_selects"] + self._stats["total_select_many"]
            return {
                "default_strategy": self._default_strategy,
                "total_selects": self._stats["total_selects"],
                "total_select_many": self._stats["total_select_many"],
                "total_operations": total,
                "strategy_usage": dict(self._stats["strategy_usage"]),
                "registered_strategies": sorted(self._strategies),
                "strategy_stats": strategy_stats,
            }