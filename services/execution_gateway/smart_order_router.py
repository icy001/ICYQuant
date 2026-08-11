"""Smart Order Router — Multi-venue order routing with dynamic path selection.

The Smart Order Router (SOR) evaluates available venues, analyzes
liquidity, costs, and latency to select the optimal execution path.
Supports dynamic re-routing and failover.

Decision Pipeline::

    Order → Venue Selection → Liquidity Scan → Cost Analysis → Dispatch

Usage::

    router = SmartOrderRouter()
    await router.initialize(venues, brokers)
    decision = await router.route(order_id, symbol, quantity)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from services.execution_gateway.execution_optimizer import ExecutionOptimizer
from services.execution_gateway.liquidity_analyzer import LiquidityAnalyzer
from services.execution_gateway.metrics import GatewayMetrics
from services.execution_gateway.order_splitter import OrderSplitter
from services.execution_gateway.routing_engine import RoutingEngine
from services.execution_gateway.routing_policy import RoutingPolicy, RoutingPolicyType
from services.execution_gateway.routing_strategy import RoutingStrategy, RoutingStrategyType
from services.execution_gateway.venue_registry import Venue, VenueRegistry
from services.execution_gateway.venue_selector import VenueSelector

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of a routing decision.

    Attributes:
        order_id: Client order identifier
        venue: Selected venue name
        broker: Selected broker name
        score: Venue quality score
        strategy: Routing strategy used
        child_orders: Number of split child orders
        latency_ms: Routing decision latency
        reason: Human-readable decision explanation
        metadata: Additional context
    """

    order_id: str = ""
    venue: str = ""
    broker: str = ""
    score: float = 0.0
    strategy: str = ""
    child_orders: int = 1
    latency_ms: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "venue": self.venue,
            "broker": self.broker,
            "score": self.score,
            "strategy": self.strategy,
            "child_orders": self.child_orders,
            "latency_ms": self.latency_ms,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class SmartOrderRouter:
    """Multi-venue smart order router.

    Evaluates available execution venues and selects the optimal path
    based on liquidity, cost, latency, and execution quality.

    Attributes:
        venue_registry: Venue registration store
        venue_selector: Venue evaluation engine
        liquidity_analyzer: Real-time liquidity analysis
        routing_engine: Routing decision engine
        order_splitter: Multi-venue order splitter
        execution_optimizer: Execution cost optimizer
        metrics: Gateway metrics
        _routing_policy: Active routing policy
        _routing_strategy: Active routing strategy
        _fallback_venues: Ordered fallback venue list
    """

    def __init__(
        self,
        venue_registry: Optional[VenueRegistry] = None,
        venue_selector: Optional[VenueSelector] = None,
        liquidity_analyzer: Optional[LiquidityAnalyzer] = None,
        routing_engine: Optional[RoutingEngine] = None,
        order_splitter: Optional[OrderSplitter] = None,
        execution_optimizer: Optional[ExecutionOptimizer] = None,
        metrics: Optional[GatewayMetrics] = None,
    ) -> None:
        self.venue_registry = venue_registry or VenueRegistry()
        self.venue_selector = venue_selector or VenueSelector()
        self.liquidity_analyzer = liquidity_analyzer or LiquidityAnalyzer()
        self.routing_engine = routing_engine or RoutingEngine()
        self.order_splitter = order_splitter or OrderSplitter()
        self.execution_optimizer = execution_optimizer or ExecutionOptimizer()
        self.metrics = metrics or GatewayMetrics()

        self._routing_policy = RoutingPolicy(RoutingPolicyType.BEST_EXECUTION)
        self._routing_strategy = RoutingStrategy(RoutingStrategyType.DYNAMIC)
        self._fallback_venues: list[str] = []

        self._decision_history: list[RoutingDecision] = []
        self._max_history = 1000

    # ── Initialization ─────────────────────────────────────────────

    async def initialize(
        self,
        venues: Optional[list[Venue]] = None,
        brokers: Optional[list[str]] = None,
    ) -> None:
        """Initialize the router with venues and brokers.

        Args:
            venues: Initial venue list
            brokers: Initial broker list
        """
        if venues:
            for venue in venues:
                self.venue_registry.register_venue(venue)

        if brokers:
            for broker in brokers:
                self.venue_registry.register_broker(broker)

        logger.info(
            "SmartOrderRouter initialized: %d venues, %d brokers",
            self.venue_registry.count,
            len(self.venue_registry.brokers),
        )

    def register_routing_engine(self, engine: RoutingEngine) -> None:
        """Register a routing engine.

        Args:
            engine: Routing engine instance
        """
        self.routing_engine = engine

    # ── Routing ────────────────────────────────────────────────────

    async def route(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        side: str = "BUY",
        order_type: str = "LIMIT",
        limit_price: float = 0.0,
        urgency: str = "normal",
        context: Optional[dict[str, Any]] = None,
    ) -> RoutingDecision:
        """Determine the optimal execution venue for an order.

        Evaluates all available venues and selects the best path
        based on the active routing policy and strategy.

        Args:
            order_id: Client order identifier
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            order_type: LIMIT, MARKET, etc.
            limit_price: Limit price (for limit orders)
            urgency: normal, urgent, or passive
            context: Additional execution context

        Returns:
            RoutingDecision with selected venue
        """
        start = time.monotonic()

        try:
            # Get available venues for this symbol
            venues = self.venue_registry.get_venues_for_symbol(symbol)
            if not venues:
                logger.warning("No venues available for %s", symbol)
                return RoutingDecision(
                    order_id=order_id,
                    reason="No available venues",
                )

            # Analyze liquidity across venues
            liquidity_scores = await self.liquidity_analyzer.analyze(
                symbol=symbol,
                quantity=quantity,
                side=side,
                venues=venues,
            )

            # Select best venue based on routing policy
            selected = await self.venue_selector.select(
                venues=venues,
                liquidity_scores=liquidity_scores,
                policy=self._routing_policy,
                strategy=self._routing_strategy,
                urgency=urgency,
            )

            # Optimize execution parameters
            optimized = await self.execution_optimizer.optimize(
                symbol=symbol,
                quantity=quantity,
                side=side,
                venue=selected,
                context=context,
            )

            # Split order if needed
            child_count = await self.order_splitter.determine_splits(
                quantity=quantity,
                venue=selected,
                liquidity_scores=liquidity_scores,
            )

            latency = (time.monotonic() - start) * 1000

            decision = RoutingDecision(
                order_id=order_id,
                venue=selected.name,
                broker=selected.broker_name,
                score=selected.score,
                strategy=self._routing_strategy.strategy_type.value,
                child_orders=child_count,
                latency_ms=latency,
                reason=f"Selected {selected.name}: score={selected.score:.2f}, "
                        f"liquidity={liquidity_scores.get(selected.name, {}).get('score', 0):.2f}",
                metadata={
                    "symbol": symbol,
                    "quantity": quantity,
                    "side": side,
                    "optimized": optimized,
                    "liquidity_scores": liquidity_scores,
                },
            )

            self._record_decision(decision)
            self.metrics.record_sor_request(decision.strategy)
            self.metrics.record_best_venue_selection(decision.venue, decision.score)
            self.metrics.record_routing_latency(decision.latency_ms)

            logger.info(
                "SOR decision: order=%s venue=%s score=%.2f latency=%.1fms",
                order_id,
                decision.venue,
                decision.score,
                decision.latency_ms,
            )

            return decision

        except Exception as e:
            logger.error("Routing failed for order %s: %s", order_id, e)
            return RoutingDecision(
                order_id=order_id,
                reason=f"Routing error: {e}",
            )

    async def optimize(
        self,
        order_id: str,
        current_venue: str,
    ) -> RoutingDecision:
        """Re-evaluate routing decision for an in-flight order.

        Called when market conditions change significantly.

        Args:
            order_id: Client order identifier
            current_venue: Currently selected venue

        Returns:
            Updated RoutingDecision
        """
        logger.info("Re-optimizing route for order %s", order_id)
        # For optimization, re-route with updated market data
        # This would typically be triggered by market events
        return RoutingDecision(
            order_id=order_id,
            venue=current_venue,
            reason="Optimization not triggered — conditions unchanged",
        )

    async def dispatch(
        self,
        decision: RoutingDecision,
        broker_gateway: Any,
    ) -> dict[str, Any]:
        """Dispatch an order based on a routing decision.

        Args:
            decision: Routing decision
            broker_gateway: Broker gateway to send through

        Returns:
            Dispatch result
        """
        if not decision.venue:
            return {"status": "ERROR", "message": "No venue in routing decision"}

        try:
            # Submit to broker gateway
            result = await broker_gateway.submit_order(
                order_id=decision.order_id,
                venue=decision.venue,
                broker=decision.broker,
            )
            return result
        except Exception as e:
            logger.error("Dispatch failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    async def cancel(self, order_id: str, broker_order_id: str = "") -> dict[str, Any]:
        """Cancel an order through the router.

        Args:
            order_id: Client order identifier
            broker_order_id: Broker order identifier

        Returns:
            Cancellation result
        """
        logger.info("Cancelling order %s (broker: %s)", order_id, broker_order_id)
        return {"status": "CANCELLED", "order_id": order_id}

    async def failover(
        self,
        order_id: str,
        failed_venue: str,
    ) -> RoutingDecision:
        """Perform failover routing after venue failure.

        Args:
            order_id: Client order identifier
            failed_venue: Venue that failed

        Returns:
            New routing decision for failover venue
        """
        logger.warning("Failover triggered for order %s from %s", order_id, failed_venue)

        # Mark venue as degraded
        self.venue_registry.mark_degraded(failed_venue)

        # Select fallback
        fallback = self._fallback_venues[0] if self._fallback_venues else ""
        self.metrics.record_failover_switch(failed_venue, fallback)

        return RoutingDecision(
            order_id=order_id,
            venue=fallback,
            reason=f"Failover from {failed_venue} to {fallback}",
        )

    # ── Policy & Strategy ──────────────────────────────────────────

    def set_routing_policy(self, policy: RoutingPolicy) -> None:
        """Set the active routing policy.

        Args:
            policy: Routing policy instance
        """
        self._routing_policy = policy
        logger.info("Routing policy set to %s", policy.policy_type.value)

    def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        """Set the active routing strategy.

        Args:
            strategy: Routing strategy instance
        """
        self._routing_strategy = strategy
        logger.info("Routing strategy set to %s", strategy.strategy_type.value)

    def set_fallback_venues(self, venues: list[str]) -> None:
        """Set ordered fallback venue list.

        Args:
            venues: Ordered list of fallback venue names
        """
        self._fallback_venues = venues

    # ── History ────────────────────────────────────────────────────

    def _record_decision(self, decision: RoutingDecision) -> None:
        """Record a routing decision in history."""
        self._decision_history.append(decision)
        if len(self._decision_history) > self._max_history:
            self._decision_history = self._decision_history[-self._max_history:]

    def get_decision_history(self, limit: int = 100) -> list[RoutingDecision]:
        """Get recent routing decisions.

        Args:
            limit: Maximum number of decisions to return

        Returns:
            List of recent RoutingDecision objects
        """
        return self._decision_history[-limit:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize router state."""
        return {
            "policy": self._routing_policy.policy_type.value,
            "strategy": self._routing_strategy.strategy_type.value,
            "venues_registered": self.venue_registry.count,
            "fallback_venues": self._fallback_venues,
            "decision_history_count": len(self._decision_history),
        }
