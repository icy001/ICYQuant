"""
Order Intent Router
===================
Routes validated order intents to appropriate destinations
(OMS, Risk Engine, execution venues).

Supports:
- Rule-based routing
- Priority-based ordering
- Destination health checking
- Failover routing
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RouteStatus(str, Enum):
    """Status of a routing attempt."""

    PENDING = "pending"
    ROUTED = "routed"
    FAILED = "failed"
    REJECTED = "rejected"
    REROUTED = "rerouted"


@dataclass
class RouteDestination:
    """A destination for order intent routing."""

    destination_id: str = ""
    name: str = ""
    type: str = "oms"  # oms, risk_engine, paper_trading, etc.
    priority: int = 1
    healthy: bool = True
    max_intents_per_batch: int = 50
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """Result of routing an order intent."""

    intent_id: str = ""
    destination_id: str = ""
    status: RouteStatus = RouteStatus.PENDING
    error: Optional[str] = None
    routed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "destination_id": self.destination_id,
            "status": self.status.value,
            "error": self.error,
            "routed_at": self.routed_at.isoformat(),
            "metadata": self.metadata,
        }


class OrderIntentRouter:
    """
    Routes validated order intents to appropriate destinations.

    The router is the bridge between the Strategy Platform and
    downstream systems (OMS, Risk Engine, execution venues).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Registered destinations
        self._destinations: Dict[str, RouteDestination] = {}

        # Routing rules: strategy_id → destination_id
        self._routing_rules: Dict[str, str] = {}

        # Default destination
        self._default_destination = self._config.get("default_destination", "primary_oms")

        # Route history
        self._route_history: List[RouteResult] = []
        self._max_history = self._config.get("max_history", 10000) if config else 10000

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Register default destinations
        destinations_config = self._config.get("destinations", {})
        for dest_id, dconfig in destinations_config.items():
            self._destinations[dest_id] = RouteDestination(
                destination_id=dest_id,
                name=dconfig.get("name", dest_id),
                type=dconfig.get("type", "oms"),
                priority=dconfig.get("priority", 1),
                healthy=dconfig.get("healthy", True),
                max_intents_per_batch=dconfig.get("max_intents_per_batch", 50),
            )

        # If no destinations configured, create a default
        if not self._destinations:
            self._destinations["primary_oms"] = RouteDestination(
                destination_id="primary_oms",
                name="Primary OMS",
                type="oms",
                priority=1,
                healthy=True,
            )

        # Load routing rules
        rules_config = self._config.get("routing_rules", {})
        self._routing_rules.update(rules_config)

        self._initialized = True
        logger.info(
            "OrderIntentRouter initialized (%d destinations)",
            len(self._destinations),
        )

    async def shutdown(self) -> None:
        self._destinations.clear()
        self._routing_rules.clear()
        self._route_history.clear()
        self._initialized = False
        logger.info("OrderIntentRouter shut down")

    # ------------------------------------------------------------------
    # Destination Management
    # ------------------------------------------------------------------

    def register_destination(self, destination: RouteDestination) -> None:
        """Register a routing destination."""
        self._destinations[destination.destination_id] = destination
        logger.info("Destination registered: %s", destination.destination_id)

    def unregister_destination(self, destination_id: str) -> bool:
        if destination_id in self._destinations:
            del self._destinations[destination_id]
            return True
        return False

    def set_destination_health(self, destination_id: str, healthy: bool) -> None:
        """Update destination health status."""
        dest = self._destinations.get(destination_id)
        if dest:
            dest.healthy = healthy
            logger.info("Destination %s health: %s", destination_id, "healthy" if healthy else "unhealthy")

    def get_destination(self, destination_id: str) -> Optional[RouteDestination]:
        return self._destinations.get(destination_id)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _resolve_destination(self, intent: Any) -> RouteDestination:
        """Determine the destination for an intent."""
        if isinstance(intent, dict):
            strategy_id = intent.get("strategy_id", "")
            explicit_dest = intent.get("destination", "")
        else:
            strategy_id = getattr(intent, "strategy_id", "")
            explicit_dest = getattr(intent, "destination", "")

        # Explicit destination override
        if explicit_dest and explicit_dest in self._destinations:
            dest = self._destinations[explicit_dest]
            if dest.healthy:
                return dest

        # Strategy-based routing rule
        if strategy_id in self._routing_rules:
            dest_id = self._routing_rules[strategy_id]
            if dest_id in self._destinations and self._destinations[dest_id].healthy:
                return self._destinations[dest_id]

        # Default destination
        default = self._destinations.get(self._default_destination)
        if default and default.healthy:
            return default

        # Fallback: first healthy destination
        for dest in sorted(self._destinations.values(), key=lambda d: d.priority, reverse=True):
            if dest.healthy:
                return dest

        # Last resort: create a null destination
        return RouteDestination(
            destination_id="null",
            name="No Healthy Destination",
            type="null",
            healthy=False,
        )

    async def route(self, intent: Any) -> RouteResult:
        """
        Route a single order intent to its destination.

        Args:
            intent: OrderIntent object or dict.

        Returns:
            RouteResult indicating success or failure.
        """
        if not self._initialized:
            await self.initialize()

        if isinstance(intent, dict):
            intent_id = intent.get("intent_id", "unknown")
        else:
            intent_id = getattr(intent, "intent_id", "unknown")

        destination = self._resolve_destination(intent)

        if not destination.healthy:
            result = RouteResult(
                intent_id=intent_id,
                destination_id=destination.destination_id,
                status=RouteStatus.FAILED,
                error=f"Destination {destination.destination_id} is unhealthy",
            )
            self._record_result(result)
            self._metrics["route_failed"] = self._metrics.get("route_failed", 0) + 1
            return result

        # Update intent with destination info
        if isinstance(intent, dict):
            intent["destination"] = destination.destination_id
            intent["route_status"] = RouteStatus.ROUTED.value
        else:
            if hasattr(intent, "destination"):
                intent.destination = destination.destination_id
            if hasattr(intent, "route_status"):
                intent.route_status = RouteStatus.ROUTED.value

        result = RouteResult(
            intent_id=intent_id,
            destination_id=destination.destination_id,
            status=RouteStatus.ROUTED,
        )
        self._record_result(result)

        self._metrics["route_success"] = self._metrics.get("route_success", 0) + 1

        logger.debug(
            "Routed intent %s → %s (%s)",
            intent_id,
            destination.destination_id,
            destination.name,
        )

        return result

    async def route_batch(self, intents: List[Any]) -> List[RouteResult]:
        """
        Route a batch of order intents.

        Groups intents by destination for efficient delivery.
        """
        if not self._initialized:
            await self.initialize()

        results = []
        for intent in intents:
            result = await self.route(intent)
            results.append(result)

        success = sum(1 for r in results if r.status == RouteStatus.ROUTED)
        logger.info(
            "Batch routing: %d/%d intents routed successfully",
            success,
            len(results),
        )

        return results

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _record_result(self, result: RouteResult) -> None:
        self._route_history.append(result)
        if len(self._route_history) > self._max_history:
            self._route_history = self._route_history[-self._max_history:]

    def get_route_history(self, limit: int = 100) -> List[RouteResult]:
        return self._route_history[-limit:]

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
