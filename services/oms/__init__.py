"""OMS/EMS Integration Layer.

Order Management System & Execution Management System providing:
- Complete order lifecycle management (creation -> settlement)
- Strict state machine enforcing valid transitions
- Broker gateway abstraction for multi-market connectivity
- Smart order routing based on fees, latency, and liquidity
- Real-time execution tracking with fill events
- Trade confirmation and reconciliation with downstream systems

Architecture:
    Strategy -> Portfolio -> Risk Engine -> OMS -> EMS -> Broker -> Exchange
"""

from .order import Order, OrderManager, OrderSide, OrderStateMachine, OrderStatus, OrderType
from .gateway import (
    BrokerAdapter,
    BrokerBalance,
    BrokerGateway,
    BrokerOrderRequest,
    BrokerOrderResponse,
    BrokerPosition,
    BrokerType,
    ConnectionStatus,
    OrderAction,
    PaperTradingGateway,
    Route,
    RouteMetric,
    RoutingDecision,
    SmartRouter,
)
from .execution import (
    ConfirmationStatus,
    ExecutionReport,
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionTracker,
    FillEvent,
    FillEventType,
    TradeConfirmation,
    TradeConfirmationEngine,
)
from .api import router as oms_router

__all__ = [
    # Order
    "Order",
    "OrderManager",
    "OrderSide",
    "OrderStateMachine",
    "OrderStatus",
    "OrderType",
    # Gateway
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
    # Execution
    "ConfirmationStatus",
    "ExecutionReport",
    "ExecutionSnapshot",
    "ExecutionStatus",
    "ExecutionTracker",
    "FillEvent",
    "FillEventType",
    "TradeConfirmation",
    "TradeConfirmationEngine",
    # API
    "oms_router",
]
