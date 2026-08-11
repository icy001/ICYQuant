"""
Execution Policy — governance rules for autonomous execution behavior.

Defines the guardrails within which the execution optimizer operates:
    - Execution time limits
    - Participation rate ceilings
    - Cost budgets
    - Venue whitelists
    - Strategy permissions
    - Emergency thresholds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPolicy:
    """Execution policy configuration."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "default"

    # Time limits
    max_execution_minutes: int = 120
    min_slice_interval_seconds: int = 30

    # Participation
    max_participation_rate: float = 0.15
    max_order_pct_adv: float = 0.10
    max_single_slice_pct_adv: float = 0.03

    # Cost
    max_expected_cost_bps: float = 50.0
    max_expected_impact_bps: float = 30.0
    max_slippage_bps: float = 100.0

    # Strategy permissions
    allowed_strategies: list[str] = field(default_factory=lambda: [
        "market", "limit", "twap", "vwap", "pov",
        "adaptive", "liquidity_seeking", "iceberg",
    ])
    allowed_venues: list[str] = field(default_factory=lambda: [
        "SMART", "PRIMARY", "SECONDARY",
    ])

    # Timing windows
    avoid_market_open_min: int = 15
    avoid_market_close_min: int = 15
    avoid_auction_periods: bool = True

    # Emergency
    max_consecutive_slippage_violations: int = 3
    cancel_on_spread_widening: float = 5.0  # Cancel if spread widens 5x
    cancel_on_vol_spike: float = 3.0  # Cancel if vol spikes 3x

    # Limits
    max_concurrent_orders: int = 20
    max_orders_per_minute: int = 10
    max_notional_per_order: float = 50_000_000

    # Validation
    require_price_reasonability: bool = True
    max_price_deviation_pct: float = 0.05

    class Meta:
        """Policy lifecycle."""
        enabled: bool = True
        version: int = 1
        created_at: datetime = field(default_factory=datetime.now)
        updated_at: Optional[datetime] = None


class ExecutionPolicyManager:
    """
    Manages execution policies and enforces policy compliance.

    Policies define the governance framework within which
    autonomous execution decisions are allowed.
    """

    def __init__(self, default_policy: Optional[ExecutionPolicy] = None) -> None:
        self._policies: dict[str, ExecutionPolicy] = {}
        if default_policy:
            self._policies[default_policy.name] = default_policy
        else:
            default = ExecutionPolicy()
            self._policies[default.name] = default

    def get_policy(self, name: str = "default") -> ExecutionPolicy:
        """Get a named policy."""
        return self._policies.get(name, self._policies["default"])

    def add_policy(self, policy: ExecutionPolicy) -> None:
        """Register a new policy."""
        self._policies[policy.name] = policy

    def validate_order(self, order: dict, policy_name: str = "default") -> list[str]:
        """Validate an order against policy."""
        policy = self.get_policy(policy_name)
        violations = []

        pct_adv = order.get("pct_adv", 0)
        if pct_adv > policy.max_order_pct_adv:
            violations.append(f"Order Pct ADV {pct_adv:.1%} exceeds {policy.max_order_pct_adv:.1%}")

        cost = order.get("expected_cost_bps", 0)
        if cost > policy.max_expected_cost_bps:
            violations.append(f"Expected cost {cost:.0f}bps exceeds {policy.max_expected_cost_bps:.0f}bps")

        strategy = order.get("strategy", "")
        if strategy and strategy not in policy.allowed_strategies:
            violations.append(f"Strategy '{strategy}' not in allowed list")

        return violations

    def is_time_allowed(self, dt: Optional[datetime] = None) -> bool:
        """Check if execution is allowed at the given time."""
        now = dt or datetime.now()
        if isinstance(now, time):
            return True
        # Market hours check would go here
        return True
