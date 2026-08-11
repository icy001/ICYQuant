"""Order Router — Broker and market routing decisions.

Routes orders to the appropriate broker gateway and exchange market
based on symbol, strategy configuration, and routing rules.

Pipeline:
    Validated Order → Symbol Analysis → Broker Selection → Market Selection → Route
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order

logger = logging.getLogger(__name__)


class RouteStatus(str, Enum):
    """Routing result status."""
    SUCCESS = "success"
    FAILED = "failed"
    NO_BROKER = "no_broker_available"
    MARKET_CLOSED = "market_closed"


@dataclass
class RouteResult:
    """Result of order routing."""
    order_id: str
    success: bool = False
    broker: str = ""
    market: str = ""
    route: str = ""
    gateway: str = ""
    status: RouteStatus = RouteStatus.FAILED
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "success": self.success,
            "broker": self.broker,
            "market": self.market,
            "route": self.route,
            "gateway": self.gateway,
            "status": self.status.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class OrderRouter:
    """Routes orders to brokers and exchange markets.

    Determines the target broker, market, and gateway for each order
    based on symbol, strategy, and configured routing rules.

    Usage::

        router = OrderRouter()
        router.register_broker("IB", markets=["US_STOCKS", "US_OPTIONS"])
        result = await router.route(order)
        if result.success:
            print(f"Routed to {result.broker} / {result.market}")
    """

    def __init__(self) -> None:
        # broker_id → BrokerConfig
        self._brokers: dict[str, BrokerConfig] = {}
        # symbol → default routing
        self._symbol_routes: dict[str, RouteConfig] = {}
        # strategy_id → preferred routing
        self._strategy_routes: dict[str, RouteConfig] = {}
        # Default fallback broker
        self._default_broker: Optional[str] = None

    async def route(self, order: Order) -> RouteResult:
        """Route an order to the appropriate broker and market.

        Args:
            order: Order to route

        Returns:
            RouteResult with broker, market, and gateway info
        """
        symbol = order.symbol.upper()

        # Check pre-configured routes
        route_config = self._resolve_route(order)

        if route_config:
            broker_id = route_config.broker
            market = route_config.market
        else:
            # Auto-select based on symbol
            broker_id, market = await self._select_broker(order)

        if not broker_id:
            return RouteResult(
                order_id=order.order_id,
                status=RouteStatus.NO_BROKER,
                reason=f"No broker available for symbol {symbol}",
            )

        broker = self._brokers.get(broker_id)
        if broker is None:
            return RouteResult(
                order_id=order.order_id,
                status=RouteStatus.NO_BROKER,
                reason=f"Broker '{broker_id}' not registered",
            )

        # Build route string
        route = f"{broker_id}:{market}" if market else broker_id

        # Update order with routing info
        order.broker = broker_id
        order.market = market or ""
        order.route = route

        logger.info(
            f"Order {order.order_id} routed to {broker_id}/{market} "
            f"for symbol {symbol}"
        )

        return RouteResult(
            order_id=order.order_id,
            success=True,
            broker=broker_id,
            market=market or "",
            route=route,
            gateway=broker.gateway,
            status=RouteStatus.SUCCESS,
            reason=f"Routed to {broker_id}",
        )

    async def _select_broker(
        self, order: Order
    ) -> tuple[Optional[str], Optional[str]]:
        """Select the best broker for an order.

        Args:
            order: Order to route

        Returns:
            Tuple of (broker_id, market) or (None, None)
        """
        symbol = order.symbol.upper()

        # Check symbol-specific routing
        if symbol in self._symbol_routes:
            config = self._symbol_routes[symbol]
            return config.broker, config.market

        # Check strategy-specific routing
        if order.strategy_id and order.strategy_id in self._strategy_routes:
            config = self._strategy_routes[order.strategy_id]
            return config.broker, config.market

        # Use default broker
        if self._default_broker and self._default_broker in self._brokers:
            broker = self._brokers[self._default_broker]
            return self._default_broker, broker.markets[0] if broker.markets else None

        return None, None

    def _resolve_route(self, order: Order) -> Optional[RouteConfig]:
        """Resolve the routing configuration for an order."""
        symbol = order.symbol.upper()
        if symbol in self._symbol_routes:
            return self._symbol_routes[symbol]
        if order.strategy_id and order.strategy_id in self._strategy_routes:
            return self._strategy_routes[order.strategy_id]
        return None

    def register_broker(
        self,
        broker_id: str,
        gateway: str = "",
        markets: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Register a broker with its markets.

        Args:
            broker_id: Unique broker identifier
            gateway: Gateway endpoint for this broker
            markets: List of supported markets
            **kwargs: Additional broker metadata
        """
        self._brokers[broker_id] = BrokerConfig(
            broker_id=broker_id,
            gateway=gateway,
            markets=markets or [],
            metadata=kwargs,
        )
        logger.info(f"Registered broker: {broker_id} (gateway={gateway})")

    def set_default_broker(self, broker_id: str) -> None:
        """Set the default fallback broker.

        Args:
            broker_id: Broker to use as default
        """
        self._default_broker = broker_id
        logger.info(f"Default broker set to: {broker_id}")

    def set_symbol_route(
        self, symbol: str, broker: str, market: str = ""
    ) -> None:
        """Configure a specific route for a symbol.

        Args:
            symbol: Trading symbol
            broker: Target broker
            market: Target market
        """
        self._symbol_routes[symbol.upper()] = RouteConfig(broker=broker, market=market)

    def set_strategy_route(
        self, strategy_id: str, broker: str, market: str = ""
    ) -> None:
        """Configure a specific route for a strategy.

        Args:
            strategy_id: Strategy identifier
            broker: Target broker
            market: Target market
        """
        self._strategy_routes[strategy_id] = RouteConfig(broker=broker, market=market)

    def to_dict(self) -> dict[str, Any]:
        """Serialize router state."""
        return {
            "brokers": {
                bid: b.to_dict() for bid, b in self._brokers.items()
            },
            "symbol_routes": {
                s: r.to_dict() for s, r in self._symbol_routes.items()
            },
            "strategy_routes": {
                s: r.to_dict() for s, r in self._strategy_routes.items()
            },
            "default_broker": self._default_broker,
        }


@dataclass
class BrokerConfig:
    """Configuration for a broker connection."""
    broker_id: str
    gateway: str = ""
    markets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker_id": self.broker_id,
            "gateway": self.gateway,
            "markets": self.markets,
            "metadata": self.metadata,
        }


@dataclass
class RouteConfig:
    """Routing configuration."""
    broker: str
    market: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"broker": self.broker, "market": self.market}
