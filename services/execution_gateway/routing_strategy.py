"""Routing Strategy — Dynamic routing strategy definitions.

Defines how the SOR adapts routing decisions over time based on
market conditions, execution progress, and venue performance.

Strategies:
    - DYNAMIC: Continuously re-evaluate based on market data
    - STATIC: Lock venue at order entry
    - ADAPTIVE: Switch venues when conditions change
    - SEQUENTIAL: Try venues in order until fill
    - PARALLEL: Split across multiple venues simultaneously

Usage::

    strategy = RoutingStrategy(RoutingStrategyType.DYNAMIC)
    strategy.evaluate_rebalance(current, market_data)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoutingStrategyType(str, Enum):
    """Routing strategy types."""

    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"
    ADAPTIVE = "ADAPTIVE"
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"


@dataclass
class RoutingStrategy:
    """Routing strategy configuration.

    Determines how venue selection adapts during order execution.

    Attributes:
        strategy_type: Strategy type identifier
        rebalance_interval_seconds: How often to re-evaluate venues
        rebalance_threshold: Minimum score improvement to trigger rebalance
        max_venue_switches: Maximum venue switches per order
        allow_parallel: Whether parallel execution is allowed
        sequential_timeout_seconds: Timeout before trying next venue
        parameters: Strategy-specific parameters
    """

    strategy_type: RoutingStrategyType = RoutingStrategyType.DYNAMIC
    rebalance_interval_seconds: float = 5.0
    rebalance_threshold: float = 0.05
    max_venue_switches: int = 3
    allow_parallel: bool = False
    sequential_timeout_seconds: float = 10.0
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def dynamic(cls, rebalance_interval: float = 5.0) -> RoutingStrategy:
        """Create a dynamic routing strategy.

        Args:
            rebalance_interval: Rebalance check interval in seconds

        Returns:
            RoutingStrategy configured for dynamic routing
        """
        return cls(
            strategy_type=RoutingStrategyType.DYNAMIC,
            rebalance_interval_seconds=rebalance_interval,
            allow_parallel=False,
        )

    @classmethod
    def static(cls) -> RoutingStrategy:
        """Create a static routing strategy.

        Returns:
            RoutingStrategy with locked venue selection
        """
        return cls(
            strategy_type=RoutingStrategyType.STATIC,
            max_venue_switches=0,
        )

    @classmethod
    def adaptive(cls, threshold: float = 0.05) -> RoutingStrategy:
        """Create an adaptive routing strategy.

        Args:
            threshold: Score improvement threshold to switch

        Returns:
            RoutingStrategy configured for adaptive routing
        """
        return cls(
            strategy_type=RoutingStrategyType.ADAPTIVE,
            rebalance_threshold=threshold,
        )

    @classmethod
    def sequential(cls, timeout: float = 10.0) -> RoutingStrategy:
        """Create a sequential routing strategy.

        Args:
            timeout: Timeout before trying next venue

        Returns:
            RoutingStrategy configured for sequential routing
        """
        return cls(
            strategy_type=RoutingStrategyType.SEQUENTIAL,
            sequential_timeout_seconds=timeout,
            allow_parallel=False,
        )

    @classmethod
    def parallel(cls, max_venues: int = 3) -> RoutingStrategy:
        """Create a parallel routing strategy.

        Args:
            max_venues: Maximum parallel venues

        Returns:
            RoutingStrategy configured for parallel execution
        """
        return cls(
            strategy_type=RoutingStrategyType.PARALLEL,
            allow_parallel=True,
            max_venue_switches=max_venues,
        )

    def should_rebalance(
        self,
        current_score: float,
        best_alternative_score: float,
        elapsed_seconds: float,
        switch_count: int,
    ) -> bool:
        """Determine if a venue rebalance should be triggered.

        Args:
            current_score: Current venue score
            best_alternative_score: Best alternative venue score
            elapsed_seconds: Time since last rebalance
            switch_count: Number of switches so far

        Returns:
            True if rebalance should occur
        """
        if self.strategy_type == RoutingStrategyType.STATIC:
            return False

        if switch_count >= self.max_venue_switches:
            return False

        if elapsed_seconds < self.rebalance_interval_seconds:
            return False

        improvement = best_alternative_score - current_score
        return improvement > self.rebalance_threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type.value,
            "rebalance_interval_seconds": self.rebalance_interval_seconds,
            "rebalance_threshold": self.rebalance_threshold,
            "max_venue_switches": self.max_venue_switches,
            "allow_parallel": self.allow_parallel,
            "sequential_timeout_seconds": self.sequential_timeout_seconds,
            "parameters": self.parameters,
        }
