"""Execution Gateway — Smart Order Routing and Broker Gateway.

Connects the EMS to real brokers and exchanges through:
- Smart Order Router: multi-venue execution path selection
- Broker Gateway: unified broker connection management
- FIX Engine: standard institutional protocol
- Multi-Protocol Gateways: WebSocket, gRPC support
- Resilience: failover routing, retry management, connection pooling

Architecture::

    EMS → Smart Order Router → Venue Selector → Broker Gateway → Exchange
         → Failover Router → Retry Manager → Connection Pool

Package exports::

    from services.execution_gateway import (
        SmartOrderRouter,
        BrokerGateway,
        FIXEngine,
    )
"""

from __future__ import annotations

from services.execution_gateway.gateway_runtime import GatewayRuntime
from services.execution_gateway.gateway_manager import GatewayManager
from services.execution_gateway.smart_order_router import SmartOrderRouter
from services.execution_gateway.routing_engine import RoutingEngine
from services.execution_gateway.routing_policy import RoutingPolicy, RoutingPolicyType
from services.execution_gateway.routing_strategy import RoutingStrategy, RoutingStrategyType
from services.execution_gateway.venue_selector import VenueSelector
from services.execution_gateway.venue_registry import VenueRegistry, Venue
from services.execution_gateway.liquidity_analyzer import LiquidityAnalyzer
from services.execution_gateway.market_microstructure import MarketMicrostructureAnalyzer
from services.execution_gateway.order_splitter import OrderSplitter
from services.execution_gateway.execution_optimizer import ExecutionOptimizer
from services.execution_gateway.latency_optimizer import LatencyOptimizer
from services.execution_gateway.broker_gateway import BrokerGateway
from services.execution_gateway.broker_registry import BrokerRegistry
from services.execution_gateway.broker_session import BrokerSession
from services.execution_gateway.broker_adapter import BrokerAdapter
from services.execution_gateway.exchange_adapter import ExchangeAdapter
from services.execution_gateway.exchange_registry import ExchangeRegistry
from services.execution_gateway.failover_router import FailoverRouter
from services.execution_gateway.retry_manager import RetryManager
from services.execution_gateway.connection_pool import ConnectionPool
from services.execution_gateway.metrics import GatewayMetrics
from services.execution_gateway.telemetry import GatewayTelemetry
from services.execution_gateway.diagnostics import GatewayDiagnostics
from services.execution_gateway.health import GatewayHealthChecker

__all__ = [
    "GatewayRuntime",
    "GatewayManager",
    "SmartOrderRouter",
    "RoutingEngine",
    "RoutingPolicy",
    "RoutingPolicyType",
    "RoutingStrategy",
    "RoutingStrategyType",
    "VenueSelector",
    "VenueRegistry",
    "Venue",
    "LiquidityAnalyzer",
    "MarketMicrostructureAnalyzer",
    "OrderSplitter",
    "ExecutionOptimizer",
    "LatencyOptimizer",
    "BrokerGateway",
    "BrokerRegistry",
    "BrokerSession",
    "BrokerAdapter",
    "ExchangeAdapter",
    "ExchangeRegistry",
    "FailoverRouter",
    "RetryManager",
    "ConnectionPool",
    "GatewayMetrics",
    "GatewayTelemetry",
    "GatewayDiagnostics",
    "GatewayHealthChecker",
]
