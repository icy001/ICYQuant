"""Gateway Manager — High-level orchestration for the execution gateway.

Coordinates the SOR, broker connections, and execution pipeline.
Provides the unified management API for all gateway operations.

Pipeline::

    GatewayManager → SmartOrderRouter → BrokerGateway → Exchange

Usage::

    manager = GatewayManager()
    await manager.initialize()
    result = await manager.execute_order(order, context)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from services.execution_gateway.broker_gateway import BrokerGateway
from services.execution_gateway.broker_registry import BrokerRegistry
from services.execution_gateway.execution_optimizer import ExecutionOptimizer
from services.execution_gateway.latency_optimizer import LatencyOptimizer
from services.execution_gateway.metrics import GatewayMetrics
from services.execution_gateway.routing_engine import RoutingEngine
from services.execution_gateway.smart_order_router import SmartOrderRouter
from services.execution_gateway.venue_registry import VenueRegistry

logger = logging.getLogger(__name__)


class GatewayManager:
    """High-level gateway orchestration manager.

    Coordinates all gateway sub-systems including routing, broker
    connections, optimization, and observability.

    Attributes:
        router: Smart order router instance
        routing_engine: Routing decision engine
        broker_registry: Broker registration store
        venue_registry: Venue registration store
        execution_optimizer: Execution cost optimizer
        latency_optimizer: Latency minimization optimizer
        metrics: Gateway metrics
        _initialized: Whether manager has been initialized
    """

    def __init__(
        self,
        router: Optional[SmartOrderRouter] = None,
        routing_engine: Optional[RoutingEngine] = None,
        broker_registry: Optional[BrokerRegistry] = None,
        venue_registry: Optional[VenueRegistry] = None,
        execution_optimizer: Optional[ExecutionOptimizer] = None,
        latency_optimizer: Optional[LatencyOptimizer] = None,
        metrics: Optional[GatewayMetrics] = None,
    ) -> None:
        self.router = router or SmartOrderRouter()
        self.routing_engine = routing_engine or RoutingEngine()
        self.broker_registry = broker_registry or BrokerRegistry()
        self.venue_registry = venue_registry or VenueRegistry()
        self.execution_optimizer = execution_optimizer or ExecutionOptimizer()
        self.latency_optimizer = latency_optimizer or LatencyOptimizer()
        self.metrics = metrics or GatewayMetrics()
        self._initialized = False
        self._initialized_at: Optional[datetime] = None

    # ── Lifecycle ──────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Initialize all gateway components.

        Registers venues, brokers, and establishes initial connections.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            logger.warning("Gateway manager already initialized")
            return True

        logger.info("Initializing gateway manager...")

        try:
            # Register default venues
            self.venue_registry.register_defaults()

            # Register routing engine with router
            self.router.register_routing_engine(self.routing_engine)

            self._initialized = True
            self._initialized_at = datetime.now(timezone.utc)
            logger.info("Gateway manager initialized successfully")
            return True
        except Exception as e:
            logger.error("Gateway manager initialization failed: %s", e)
            return False

    # ── Order Execution ────────────────────────────────────────────

    async def execute_order(
        self,
        order_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute an order through the gateway pipeline.

        Args:
            order_data: Order parameters (symbol, side, qty, etc.)
            context: Optional execution context

        Returns:
            Execution result with routing decision and broker response
        """
        if not self._initialized:
            return {"status": "ERROR", "message": "Gateway manager not initialized"}

        try:
            # Optimize execution parameters
            optimized = await self.execution_optimizer.optimize(order_data)

            # Route to best venue
            decision = await self.router.route(
                order_id=order_data.get("order_id", ""),
                symbol=order_data.get("symbol", ""),
                quantity=order_data.get("quantity", 0),
            )

            # Record metrics
            self.metrics.record_sor_request(decision.get("strategy", "unknown"))
            self.metrics.record_best_venue_selection(
                decision.get("venue", ""), decision.get("score", 0.0)
            )

            return {
                "status": "ROUTED",
                "routing_decision": decision,
                "optimized": optimized,
            }
        except Exception as e:
            logger.error("Order execution failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    async def cancel_order(
        self,
        order_id: str,
        broker_order_id: str = "",
    ) -> dict[str, Any]:
        """Cancel an order through the gateway.

        Args:
            order_id: Client order identifier
            broker_order_id: Broker order identifier

        Returns:
            Cancellation result
        """
        if not self._initialized:
            return {"status": "ERROR", "message": "Gateway manager not initialized"}

        try:
            await self.router.cancel(order_id, broker_order_id)
            return {"status": "CANCELLED", "order_id": order_id}
        except Exception as e:
            logger.error("Order cancellation failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    # ── Broker Management ──────────────────────────────────────────

    async def register_broker(
        self,
        name: str,
        gateway: BrokerGateway,
    ) -> bool:
        """Register a new broker gateway.

        Args:
            name: Broker identifier
            gateway: Broker gateway instance

        Returns:
            True if registered successfully
        """
        return self.broker_registry.register(name, gateway)

    async def connect_broker(self, name: str, **credentials) -> bool:
        """Connect to a registered broker.

        Args:
            name: Broker identifier
            **credentials: Authentication credentials

        Returns:
            True if connected successfully
        """
        return self.broker_registry.connect(name, **credentials)

    # ── Query ──────────────────────────────────────────────────────

    async def get_status(self) -> dict[str, Any]:
        """Get comprehensive gateway status.

        Returns:
            Status dictionary
        """
        return {
            "initialized": self._initialized,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "brokers": self.broker_registry.count,
            "venues": self.venue_registry.count,
            "router": self.router.to_dict(),
            "metrics": self.metrics.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "initialized": self._initialized,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "brokers": self.broker_registry.count,
            "venues": self.venue_registry.count,
        }
