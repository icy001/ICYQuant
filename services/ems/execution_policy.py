"""Execution Policy — Execution policy configuration and enforcement.

Defines execution policies that govern how orders are executed,
including risk controls, venue preferences, and behavior rules.

Policies:
    - Slippage Limit: Maximum allowed deviation from benchmark
    - Participation Limit: Maximum market participation rate
    - Venue Preference: Preferred execution venues
    - Time Limit: Maximum execution duration
    - Urgency: Execution aggressiveness level

Usage::

    policy = ExecutionPolicy(
        max_slippage_bps=5.0,
        max_participation_rate=0.1,
        preferred_venues=["NYSE", "NASDAQ"],
    )
    policy.validate_fill(fill_price=150.5, benchmark=150.0)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UrgencyLevel(str, Enum):
    """Execution urgency / aggressiveness level.

    PASSIVE: Minimize market impact, maximize price improvement
    NEUTRAL: Balance speed and cost
    AGGRESSIVE: Prioritize speed of execution
    """

    PASSIVE = "PASSIVE"
    NEUTRAL = "NEUTRAL"
    AGGRESSIVE = "AGGRESSIVE"


@dataclass
class ExecutionPolicy:
    """Execution policy governing order execution behavior.

    Attributes:
        max_slippage_bps: Maximum slippage in basis points
        max_participation_rate: Maximum market participation rate (0-1)
        preferred_venues: Ordered list of preferred venues
        excluded_venues: Venues to avoid
        max_duration_seconds: Maximum execution duration
        urgency: Execution urgency level
        require_venue_confirmation: Require venue ack before execution
        min_fill_ratio: Minimum fill ratio before pausing
        max_child_order_pct: Maximum child order as % of market volume
        tags: Arbitrary policy tags
    """

    max_slippage_bps: float = 10.0
    max_participation_rate: float = 0.10
    preferred_venues: list[str] = field(default_factory=list)
    excluded_venues: list[str] = field(default_factory=list)
    max_duration_seconds: float = 3600.0
    urgency: UrgencyLevel = UrgencyLevel.NEUTRAL
    require_venue_confirmation: bool = False
    min_fill_ratio: float = 0.0
    max_child_order_pct: float = 0.05
    tags: dict[str, str] = field(default_factory=dict)

    def validate_fill(
        self,
        fill_price: float,
        benchmark_price: float,
    ) -> tuple[bool, str]:
        """Validate a fill against policy limits.

        Args:
            fill_price: Actual fill price
            benchmark_price: Benchmark/reference price

        Returns:
            Tuple of (is_valid, reason)
        """
        if benchmark_price <= 0:
            return True, "No benchmark"

        slippage_bps = abs(fill_price - benchmark_price) / benchmark_price * 10000

        if slippage_bps > self.max_slippage_bps:
            msg = f"Slippage {slippage_bps:.1f} bps exceeds limit {self.max_slippage_bps:.1f} bps"
            logger.warning(msg)
            return False, msg

        return True, f"Slippage {slippage_bps:.1f} bps within limit"

    def validate_participation(self, participation_rate: float) -> tuple[bool, str]:
        """Validate market participation rate.

        Args:
            participation_rate: Current participation rate (0-1)

        Returns:
            Tuple of (is_valid, reason)
        """
        if participation_rate > self.max_participation_rate:
            msg = f"Participation {participation_rate:.2%} exceeds limit {self.max_participation_rate:.2%}"
            logger.warning(msg)
            return False, msg
        return True, f"Participation {participation_rate:.2%} within limit"

    def validate_duration(self, elapsed_seconds: float) -> tuple[bool, str]:
        """Validate execution duration.

        Args:
            elapsed_seconds: Elapsed execution time

        Returns:
            Tuple of (is_valid, reason)
        """
        if elapsed_seconds > self.max_duration_seconds:
            msg = f"Duration {elapsed_seconds:.1f}s exceeds limit {self.max_duration_seconds:.1f}s"
            logger.warning(msg)
            return False, msg
        return True, f"Duration {elapsed_seconds:.1f}s within limit"

    def is_venue_allowed(self, venue: str) -> bool:
        """Check if a venue is allowed by this policy.

        Args:
            venue: Venue identifier

        Returns:
            True if venue is allowed
        """
        if venue in self.excluded_venues:
            return False
        if self.preferred_venues and venue not in self.preferred_venues:
            return False
        return True

    def get_best_venue(self, venues: list[str]) -> Optional[str]:
        """Select the best venue based on policy preferences.

        Args:
            venues: Available venues

        Returns:
            Best venue or None
        """
        allowed = [v for v in venues if self.is_venue_allowed(v)]
        if not allowed:
            return None

        # Sort by preferred order
        if self.preferred_venues:
            allowed.sort(key=lambda v: self.preferred_venues.index(v) if v in self.preferred_venues else 999)

        return allowed[0]

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy to dictionary."""
        return {
            "max_slippage_bps": self.max_slippage_bps,
            "max_participation_rate": self.max_participation_rate,
            "preferred_venues": self.preferred_venues,
            "excluded_venues": self.excluded_venues,
            "max_duration_seconds": self.max_duration_seconds,
            "urgency": self.urgency.value,
            "require_venue_confirmation": self.require_venue_confirmation,
            "min_fill_ratio": self.min_fill_ratio,
            "max_child_order_pct": self.max_child_order_pct,
            "tags": self.tags,
        }
