"""Execution Optimizer — Execution cost and quality optimization.

Optimizes execution parameters to minimize total trading costs including
explicit fees, market impact, and opportunity cost.

Optimization Dimensions:
    - Market Impact minimization
    - Timing / Urgency optimization
    - Order type selection
    - Limit price optimization
    - Venue-specific parameter tuning

Usage::

    optimizer = ExecutionOptimizer()
    optimized = await optimizer.optimize(symbol, quantity, side, venue)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Execution parameter optimization result.

    Attributes:
        symbol: Trading symbol
        recommended_type: Recommended order type
        recommended_limit: Suggested limit price
        urgency: Execution urgency (low, normal, high)
        expected_cost_bps: Total expected cost in bps
        market_impact_bps: Estimated market impact
        fee_bps: Expected fee cost
        timing_cost_bps: Expected timing/opportunity cost
        optimal_participation_rate: Optimal % of volume
        child_order_size: Recommended child order size
        parameters: Additional optimized parameters
    """

    symbol: str = ""
    recommended_type: str = "LIMIT"
    recommended_limit: float = 0.0
    urgency: str = "normal"
    expected_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    fee_bps: float = 0.0
    timing_cost_bps: float = 0.0
    optimal_participation_rate: float = 0.1
    child_order_size: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "recommended_type": self.recommended_type,
            "recommended_limit": self.recommended_limit,
            "urgency": self.urgency,
            "expected_cost_bps": self.expected_cost_bps,
            "market_impact_bps": self.market_impact_bps,
            "fee_bps": self.fee_bps,
            "timing_cost_bps": self.timing_cost_bps,
            "optimal_participation_rate": self.optimal_participation_rate,
            "child_order_size": self.child_order_size,
            "parameters": self.parameters,
        }


class ExecutionOptimizer:
    """Execution cost and quality optimizer.

    Computes optimal execution parameters to minimize total trading
    costs across all dimensions.

    Attributes:
        _risk_aversion: Risk aversion parameter (0-1)
        _urgency_weight: Weight for urgency in cost calculation
        _impact_model: Market impact model type
        _max_participation_rate: Maximum participation rate
    """

    def __init__(
        self,
        risk_aversion: float = 0.5,
        max_participation_rate: float = 0.25,
    ) -> None:
        self._risk_aversion = risk_aversion
        self._max_participation_rate = max_participation_rate
        self._impact_model = "square_root"

    # ── Optimization ───────────────────────────────────────────────

    async def optimize(
        self,
        symbol: str,
        quantity: float,
        side: str = "BUY",
        venue: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> OptimizationResult:
        """Optimize execution parameters for an order.

        Args:
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            venue: Target venue (Venue or dict with venue info)
            context: Additional context (market data, constraints)

        Returns:
            OptimizationResult with recommended parameters
        """
        context = context or {}

        # Get venue characteristics
        venue_fee = self._get_venue_fee(venue)
        venue_depth = self._get_venue_depth(venue, context)

        # Estimate market impact
        market_impact = self._estimate_market_impact(
            quantity=quantity,
            depth_bps=venue_depth,
            participation_rate=0.1,
        )

        # Estimate timing cost (opportunity cost of delayed execution)
        timing_cost = self._estimate_timing_cost(
            risk_aversion=self._risk_aversion,
            quantity=quantity,
            depth_bps=venue_depth,
        )

        # Total expected cost
        total_cost = market_impact + venue_fee + timing_cost

        # Determine order type
        recommended_type = self._recommend_order_type(
            quantity=quantity,
            depth_bps=venue_depth,
            spread_bps=context.get("spread_bps", 2.0),
        )

        # Optimal participation rate
        optimal_participation = self._optimal_participation_rate(
            quantity=quantity,
            depth_bps=venue_depth,
        )

        # Child order size
        child_size = quantity * 0.1  # Default 10% per child

        # Urgency based on risk aversion
        urgency = (
            "high" if self._risk_aversion > 0.7
            else "low" if self._risk_aversion < 0.3
            else "normal"
        )

        return OptimizationResult(
            symbol=symbol,
            recommended_type=recommended_type,
            recommended_limit=context.get("reference_price", 0.0),
            urgency=urgency,
            expected_cost_bps=total_cost,
            market_impact_bps=market_impact,
            fee_bps=venue_fee,
            timing_cost_bps=timing_cost,
            optimal_participation_rate=optimal_participation,
            child_order_size=child_size,
            parameters={
                "risk_aversion": self._risk_aversion,
                "impact_model": self._impact_model,
                "venue_depth_bps": venue_depth,
            },
        )

    # ── Cost Estimation ────────────────────────────────────────────

    def _estimate_market_impact(
        self,
        quantity: float,
        depth_bps: float,
        participation_rate: float = 0.1,
    ) -> float:
        """Estimate market impact using square-root model.

        Args:
            quantity: Order quantity
            depth_bps: Market depth in bps
            participation_rate: Participation rate

        Returns:
            Estimated impact in bps
        """
        if depth_bps <= 0:
            return 50.0  # High impact if no depth data

        # Square-root impact model
        participation = min(quantity / depth_bps, 1.0)
        impact = math.sqrt(participation) * 50.0

        return min(impact, 100.0)

    def _estimate_timing_cost(
        self,
        risk_aversion: float,
        quantity: float,
        depth_bps: float,
    ) -> float:
        """Estimate timing / opportunity cost.

        Args:
            risk_aversion: Risk aversion parameter
            quantity: Order quantity
            depth_bps: Market depth

        Returns:
            Estimated timing cost in bps
        """
        if depth_bps <= 0:
            return 20.0

        participation = min(quantity / depth_bps, 1.0)
        # Higher risk aversion → higher timing cost (want to execute faster)
        return participation * risk_aversion * 30.0

    def _optimal_participation_rate(
        self,
        quantity: float,
        depth_bps: float,
    ) -> float:
        """Compute optimal participation rate.

        Balances market impact against timing risk.

        Args:
            quantity: Order quantity
            depth_bps: Market depth

        Returns:
            Optimal participation rate (0-1)
        """
        if depth_bps <= 0:
            return self._max_participation_rate

        # Higher risk aversion → faster execution → higher participation
        base_rate = self._risk_aversion * self._max_participation_rate

        # Adjust for order size relative to depth
        size_ratio = quantity / depth_bps
        adjusted = base_rate * (1.0 - size_ratio * 0.5)

        return max(0.05, min(adjusted, self._max_participation_rate))

    def _recommend_order_type(
        self,
        quantity: float,
        depth_bps: float,
        spread_bps: float,
    ) -> str:
        """Recommend order type based on conditions.

        Args:
            quantity: Order quantity
            depth_bps: Market depth
            spread_bps: Bid-ask spread

        Returns:
            Recommended order type string
        """
        size_ratio = quantity / max(depth_bps, 1.0)

        if spread_bps > 10.0:
            # Wide spread → use limit orders
            return "LIMIT"
        elif size_ratio > 0.5:
            # Large order → use algorithmic/iceberg
            return "ICEBERG"
        elif self._risk_aversion > 0.7:
            # High urgency → use market orders
            return "MARKET"
        else:
            return "LIMIT"

    def _get_venue_fee(self, venue: Any) -> float:
        """Extract venue fee in bps.

        Args:
            venue: Venue object or dict

        Returns:
            Fee in bps
        """
        if venue is None:
            return 1.0
        if isinstance(venue, dict):
            return venue.get("fee_bps", 1.0)
        return getattr(venue, "fee_bps", 1.0)

    def _get_venue_depth(self, venue: Any, context: dict[str, Any]) -> float:
        """Extract venue depth.

        Args:
            venue: Venue object or dict
            context: Additional context

        Returns:
            Depth in bps
        """
        if isinstance(venue, dict):
            return venue.get("depth_bps", context.get("depth_bps", 50.0))
        return context.get("depth_bps", 50.0)

    # ── Configuration ──────────────────────────────────────────────

    def set_risk_aversion(self, risk_aversion: float) -> None:
        """Set risk aversion parameter.

        Args:
            risk_aversion: Risk aversion (0-1, higher = more aggressive)
        """
        self._risk_aversion = max(0.0, min(1.0, risk_aversion))

    def to_dict(self) -> dict[str, Any]:
        """Serialize optimizer state."""
        return {
            "risk_aversion": self._risk_aversion,
            "max_participation_rate": self._max_participation_rate,
            "impact_model": self._impact_model,
        }
