"""Algorithm Strategy Registry — Strategy registration and lookup.

Provides a registry for execution algorithms, allowing dynamic
registration and discovery of execution strategies.

Usage::

    registry = StrategyRegistry()
    registry.register(TWAPStrategy())
    strategy = registry.get("TWAP")
    names = registry.list_strategies()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Registry for execution algorithm strategies.

    Maintains a catalog of available execution algorithms and
    provides lookup by name. Supports dynamic registration of
    custom strategies.

    Attributes:
        _strategies: Map of strategy name → ExecutionStrategy instance
    """

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutionStrategy] = {}

        # Auto-register built-in strategies
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in execution strategies."""
        from services.ems.algorithm.twap import TWAPStrategy
        from services.ems.algorithm.vwap import VWAPStrategy
        from services.ems.algorithm.pov import POVStrategy
        from services.ems.algorithm.iceberg import IcebergStrategy
        from services.ems.algorithm.arrival_price import ArrivalPriceStrategy
        from services.ems.algorithm.adaptive import AdaptiveStrategy

        self.register(TWAPStrategy())
        self.register(VWAPStrategy())
        self.register(POVStrategy())
        self.register(IcebergStrategy())
        self.register(ArrivalPriceStrategy())
        self.register(AdaptiveStrategy())

        logger.info("Registered %d built-in execution strategies", len(self._strategies))

    # ── Registration ───────────────────────────────────────────────

    def register(self, strategy: ExecutionStrategy) -> None:
        """Register an execution strategy.

        Args:
            strategy: Strategy instance to register
        """
        name = strategy.name
        self._strategies[name] = strategy
        logger.debug("Strategy registered: %s", name)

    def unregister(self, name: str) -> bool:
        """Unregister a strategy.

        Args:
            name: Strategy name

        Returns:
            True if unregistered
        """
        if name in self._strategies:
            del self._strategies[name]
            return True
        return False

    # ── Lookup ─────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ExecutionStrategy]:
        """Get a strategy by name (case-insensitive).

        Args:
            name: Strategy name (e.g., "TWAP", "VWAP")

        Returns:
            ExecutionStrategy instance or None
        """
        # Case-insensitive lookup
        name_upper = name.upper()
        for sname, strategy in self._strategies.items():
            if sname.upper() == name_upper:
                return strategy
        return None

    def list_strategies(self) -> list[str]:
        """List all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def has(self, name: str) -> bool:
        """Check if a strategy is registered.

        Args:
            name: Strategy name

        Returns:
            True if registered
        """
        return self.get(name) is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "strategies": self.list_strategies(),
            "count": len(self._strategies),
        }
