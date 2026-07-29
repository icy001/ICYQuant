"""Smart Order Router.

Routes orders to optimal broker/market based on:
- Trading fees (commission, exchange fees)
- Latency (execution speed)
- Liquidity (available volume at best prices)
- Fill probability (likelihood of execution)
- Market hours (exchange open/close)

For example, an NVDA order could route to:
    NASDAQ -> IBKR
    or
    NYSE -> Local Broker

The router scores each route and selects the best one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class RouteMetric(str, Enum):
    """Factors used in route scoring."""

    FEE = "fee"               # Lower is better
    LATENCY = "latency"        # Lower is better
    LIQUIDITY = "liquidity"    # Higher is better
    FILL_PROBABILITY = "fill_probability"  # Higher is better
    SPREAD = "spread"          # Lower is better


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class Route:
    """A possible route for order execution.

    Example:
        Route(
            name="NASDAQ_IBKR",
            broker="IBKR",
            market="NASDAQ",
            currency="USD",
            fee_bps=0.35,
            latency_ms=5,
            liquidity_score=0.95,
            fill_probability=0.98,
        )
    """

    name: str
    broker: str
    market: str
    currency: str = "USD"
    fee_bps: float = 0.0           # Fee in basis points
    latency_ms: float = 0.0        # Expected latency in milliseconds
    liquidity_score: float = 0.0   # 0.0 - 1.0
    fill_probability: float = 0.0  # 0.0 - 1.0
    spread_bps: float = 0.0        # Typical spread in basis points
    min_order_size: float = 0.0    # Minimum order size
    max_order_size: float = float("inf")  # Maximum order size
    is_open: bool = True           # Market open status
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """Result of routing an order."""

    order_id: str
    selected_route: Route
    reason: str
    score: float
    alternative_routes: List[Route] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# Smart Router
# =============================================================================


class SmartRouter:
    """Intelligent order routing engine.

    Evaluates available routes for an order and selects the optimal
    one based on a weighted scoring model.

    Usage:
        router = SmartRouter()
        router.register_route(Route(name="NASDAQ_IBKR", broker="IBKR", ...))
        router.register_route(Route(name="NYSE_LOCAL", broker="LOCAL", ...))

        decision = router.route(order_id="ORD_001", symbol="NVDA", quantity=10000)
        print(decision.selected_route.name)
    """

    def __init__(self) -> None:
        self._routes: Dict[str, Route] = {}

        # Default weights for scoring (all sum to 1.0)
        self._weights: Dict[RouteMetric, float] = {
            RouteMetric.FEE: 0.15,
            RouteMetric.LATENCY: 0.20,
            RouteMetric.LIQUIDITY: 0.30,
            RouteMetric.FILL_PROBABILITY: 0.25,
            RouteMetric.SPREAD: 0.10,
        }

    @property
    def routes(self) -> Dict[str, Route]:
        """All registered routes."""
        return dict(self._routes)

    @property
    def weights(self) -> Dict[RouteMetric, float]:
        """Current scoring weights."""
        return dict(self._weights)

    def register_route(self, route: Route) -> None:
        """Register a new execution route.

        Args:
            route: Route definition
        """
        self._routes[route.name] = route

    def remove_route(self, name: str) -> None:
        """Remove a registered route.

        Args:
            name: Route name to remove
        """
        self._routes.pop(name, None)

    def set_weights(self, weights: Dict[RouteMetric, float]) -> None:
        """Update scoring weights.

        Args:
            weights: New weights dictionary

        Raises:
            ValueError: If weights don't sum to 1.0
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        self._weights = dict(weights)

    def get_available_routes(
        self,
        symbol: str = "",
        quantity: float = 0.0,
        market: str = "",
    ) -> List[Route]:
        """Get available routes filtered by criteria.

        Args:
            symbol: Filter by symbol (market matching)
            market: Filter by specific market
            quantity: Filter by order size constraints

        Returns:
            List of available routes
        """
        routes = list(self._routes.values())

        if market:
            routes = [r for r in routes if r.market.upper() == market.upper()]

        routes = [r for r in routes if r.is_open]

        if quantity > 0:
            routes = [
                r for r in routes
                if r.min_order_size <= quantity <= r.max_order_size
            ]

        return routes

    def route(
        self,
        order_id: str,
        symbol: str = "",
        quantity: float = 0.0,
        preferred_broker: str = "",
        preferred_market: str = "",
    ) -> RoutingDecision:
        """Route an order to the best available route.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            quantity: Order quantity
            preferred_broker: Preferred broker (if available)
            preferred_market: Preferred market (if available)

        Returns:
            RoutingDecision with selected route and alternatives

        Raises:
            ValueError: If no routes are available
        """
        routes = self.get_available_routes(
            symbol=symbol,
            quantity=quantity,
            market=preferred_market,
        )

        if not routes:
            raise ValueError(f"No available routes for {symbol} qty={quantity}")

        # If preferred broker is available, use it
        if preferred_broker:
            preferred = [r for r in routes if r.broker == preferred_broker]
            if preferred:
                routes = preferred

        # Score all routes
        scores: Dict[str, float] = {}
        for route in routes:
            scores[route.name] = self._score_route(route)

        # Select best route
        best_route = max(routes, key=lambda r: scores[r.name])
        best_score = scores[best_route.name]

        alternatives = sorted(
            [r for r in routes if r.name != best_route.name],
            key=lambda r: scores[r.name],
            reverse=True,
        )

        reason = self._build_reason(best_route, best_score)

        return RoutingDecision(
            order_id=order_id,
            selected_route=best_route,
            reason=reason,
            score=best_score,
            alternative_routes=alternatives,
            scores=scores,
        )

    def _score_route(self, route: Route) -> float:
        """Calculate a composite score for a route.

        Higher score = better route.

        Args:
            route: Route to score

        Returns:
            Composite score (0.0 - 1.0)
        """
        # Normalize each metric to 0-1 where 1 is best
        fee_score = max(0.0, 1.0 - (route.fee_bps / 10.0))          # 0 bps = 1.0, 10 bps = 0.0
        latency_score = max(0.0, 1.0 - (route.latency_ms / 200.0))   # 0ms = 1.0, 200ms = 0.0
        liquidity_score = route.liquidity_score                        # Already 0-1
        fill_score = route.fill_probability                            # Already 0-1
        spread_score = max(0.0, 1.0 - (route.spread_bps / 20.0))     # 0 bps = 1.0, 20 bps = 0.0

        score = (
            self._weights[RouteMetric.FEE] * fee_score
            + self._weights[RouteMetric.LATENCY] * latency_score
            + self._weights[RouteMetric.LIQUIDITY] * liquidity_score
            + self._weights[RouteMetric.FILL_PROBABILITY] * fill_score
            + self._weights[RouteMetric.SPREAD] * spread_score
        )

        return score

    def _build_reason(self, route: Route, score: float) -> str:
        """Build a human-readable routing decision reason.

        Args:
            route: Selected route
            score: Composite score

        Returns:
            Human-readable reason string
        """
        parts = [
            f"Route '{route.name}' selected with score {score:.4f}",
            f"Broker: {route.broker}, Market: {route.market}",
            f"Fee: {route.fee_bps}bps, Latency: {route.latency_ms}ms",
            f"Liquidity: {route.liquidity_score:.2f}, Fill prob: {route.fill_probability:.2f}",
        ]
        return "; ".join(parts)
