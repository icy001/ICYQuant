"""Resolve strategy enum and configuration.

Provides ``ResolveStrategy`` enumeration for supported load
balancing strategies and ``StrategyConfig`` for strategy-specific
configuration parameters.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ResolveStrategy(Enum):
    """Supported service resolution / load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    WEIGHTED = "weighted"
    LEAST_CONNECTION = "least_connection"
    LEAST_LATENCY = "least_latency"
    CONSISTENT_HASH = "consistent_hash"
    LOCALITY = "locality"


class StrategyConfig:
    """Configuration for a resolution strategy.

    Stores strategy-specific key/value pairs and provides
    dictionary-like access for reading and updating them.

    Args:
        strategy: The ``ResolveStrategy`` this config applies to.
        **kwargs: Additional configuration key/value pairs.
    """

    __slots__ = ("strategy", "_params", "_lock")

    def __init__(
        self,
        strategy: ResolveStrategy = ResolveStrategy.ROUND_ROBIN,
        **kwargs: Any,
    ) -> None:
        self.strategy = strategy
        self._params: Dict[str, Any] = dict(kwargs)
        self._lock = __import__("threading").RLock()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the strategy configuration to a dictionary.

        Returns:
            Dictionary with strategy name and all parameters.
        """
        with self._lock:
            return {
                "strategy": self.strategy.value,
                "params": dict(self._params),
            }

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration parameter by key.

        Args:
            key: The parameter name.
            default: Value to return if the key is absent.

        Returns:
            The parameter value or the default.
        """
        with self._lock:
            return self._params.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration parameter.

        Args:
            key: The parameter name.
            value: The value to set.
        """
        with self._lock:
            self._params[key] = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StrategyConfig):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"StrategyConfig(strategy={self.strategy.value!r}, "
            f"params={self._params!r})"
        )