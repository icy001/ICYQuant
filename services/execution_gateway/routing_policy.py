"""Routing Policy — Policy definitions for smart order routing.

Defines the rules and constraints that govern routing decisions.
Policies determine the objective function the routing engine optimizes.

Policies:
    - BEST_EXECUTION: Optimize for best overall execution quality
    - LOWEST_COST: Minimize explicit and implicit trading costs
    - LOWEST_LATENCY: Minimize order-to-acknowledgement time
    - MAX_LIQUIDITY: Prefer venues with deepest liquidity
    - CUSTOM: User-defined weights

Usage::

    policy = RoutingPolicy(RoutingPolicyType.BEST_EXECUTION)
    engine.set_weights(**policy.weights)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoutingPolicyType(str, Enum):
    """Predefined routing policy types."""

    BEST_EXECUTION = "BEST_EXECUTION"
    LOWEST_COST = "LOWEST_COST"
    LOWEST_LATENCY = "LOWEST_LATENCY"
    MAX_LIQUIDITY = "MAX_LIQUIDITY"
    BALANCED = "BALANCED"
    CUSTOM = "CUSTOM"


# Predefined weight profiles for each policy type
_POLICY_WEIGHTS: dict[RoutingPolicyType, dict[str, float]] = {
    RoutingPolicyType.BEST_EXECUTION: {
        "liquidity": 0.30,
        "cost": 0.25,
        "latency": 0.15,
        "quality": 0.20,
        "reliability": 0.10,
    },
    RoutingPolicyType.LOWEST_COST: {
        "liquidity": 0.15,
        "cost": 0.50,
        "latency": 0.10,
        "quality": 0.15,
        "reliability": 0.10,
    },
    RoutingPolicyType.LOWEST_LATENCY: {
        "liquidity": 0.15,
        "cost": 0.10,
        "latency": 0.50,
        "quality": 0.10,
        "reliability": 0.15,
    },
    RoutingPolicyType.MAX_LIQUIDITY: {
        "liquidity": 0.55,
        "cost": 0.10,
        "latency": 0.10,
        "quality": 0.15,
        "reliability": 0.10,
    },
    RoutingPolicyType.BALANCED: {
        "liquidity": 0.20,
        "cost": 0.20,
        "latency": 0.20,
        "quality": 0.20,
        "reliability": 0.20,
    },
}


@dataclass
class RoutingPolicy:
    """Routing policy with configurable constraints.

    Attributes:
        policy_type: Policy type identifier
        weights: Factor weights for routing engine
        max_venues: Maximum venues to split across
        min_score_threshold: Minimum venue score to consider
        prefer_primary: Whether to prefer primary venue
        max_slippage_bps: Maximum acceptable slippage
        constraints: Additional policy constraints
    """

    policy_type: RoutingPolicyType = RoutingPolicyType.BEST_EXECUTION
    weights: dict[str, float] = field(default_factory=dict)
    max_venues: int = 3
    min_score_threshold: float = 0.1
    prefer_primary: bool = True
    max_slippage_bps: float = 50.0
    constraints: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.weights and self.policy_type in _POLICY_WEIGHTS:
            self.weights = dict(_POLICY_WEIGHTS[self.policy_type])

    @classmethod
    def best_execution(cls) -> RoutingPolicy:
        """Create a best execution policy.

        Returns:
            RoutingPolicy configured for best execution
        """
        return cls(policy_type=RoutingPolicyType.BEST_EXECUTION)

    @classmethod
    def lowest_cost(cls) -> RoutingPolicy:
        """Create a lowest cost policy.

        Returns:
            RoutingPolicy configured for lowest cost
        """
        return cls(policy_type=RoutingPolicyType.LOWEST_COST)

    @classmethod
    def lowest_latency(cls) -> RoutingPolicy:
        """Create a lowest latency policy.

        Returns:
            RoutingPolicy configured for lowest latency
        """
        return cls(policy_type=RoutingPolicyType.LOWEST_LATENCY)

    @classmethod
    def max_liquidity(cls) -> RoutingPolicy:
        """Create a max liquidity policy.

        Returns:
            RoutingPolicy configured for max liquidity
        """
        return cls(policy_type=RoutingPolicyType.MAX_LIQUIDITY)

    @classmethod
    def custom(cls, weights: dict[str, float], **constraints) -> RoutingPolicy:
        """Create a custom policy with user-defined weights.

        Args:
            weights: Custom factor weights
            **constraints: Additional constraints

        Returns:
            RoutingPolicy with custom configuration
        """
        return cls(
            policy_type=RoutingPolicyType.CUSTOM,
            weights=weights,
            constraints=dict(constraints),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_type": self.policy_type.value,
            "weights": self.weights,
            "max_venues": self.max_venues,
            "min_score_threshold": self.min_score_threshold,
            "prefer_primary": self.prefer_primary,
            "max_slippage_bps": self.max_slippage_bps,
            "constraints": self.constraints,
        }
