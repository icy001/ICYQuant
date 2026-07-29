"""Gateway module — broker connections, routing, and protocol adaptation."""

from .broker_gateway import (
    BrokerBalance,
    BrokerGateway,
    BrokerOrderRequest,
    BrokerOrderResponse,
    BrokerPosition,
    BrokerType,
    ConnectionStatus,
    OrderAction,
    PaperTradingGateway,
)
from .router import Route, RouteMetric, RoutingDecision, SmartRouter
from .adapter import BrokerAdapter

__all__ = [
    "BrokerAdapter",
    "BrokerBalance",
    "BrokerGateway",
    "BrokerOrderRequest",
    "BrokerOrderResponse",
    "BrokerPosition",
    "BrokerType",
    "ConnectionStatus",
    "OrderAction",
    "PaperTradingGateway",
    "Route",
    "RouteMetric",
    "RoutingDecision",
    "SmartRouter",
]
