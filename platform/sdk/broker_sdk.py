"""
ICYQuant Platform SDK - Broker SDK

Interface for broker adapter plugins.
Supports multiple brokers: IBKR, Alpaca, Interactive Brokers, etc.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

from . import PluginBase


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING = "trailing"
    ICEBERG = "iceberg"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class BrokerOrder:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filled_quantity: float = 0
    avg_fill_price: float = 0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "filledQuantity": self.filled_quantity,
            "avgFillPrice": self.avg_fill_price,
        }


@dataclass
class BrokerPosition:
    symbol: str
    quantity: float
    avg_cost: float = 0
    market_price: float = 0
    unrealized_pnl: float = 0
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avgCost": self.avg_cost,
            "marketPrice": self.market_price,
            "unrealizedPnL": self.unrealized_pnl,
        }


class BrokerAdapterPlugin(PluginBase):
    """
    Abstract base class for broker adapter plugins.

    Broker adapters must implement:
    - submit_order(order): Submit an order
    - cancel_order(order_id): Cancel an order
    - get_positions(): Get current positions
    - get_balance(): Get account balance
    """

    def __init__(self, broker_name: str = "generic"):
        super().__init__()
        self._broker_name = broker_name
        self._orders: Dict[str, BrokerOrder] = {}
        self._positions: Dict[str, BrokerPosition] = {}
        self._balance: float = 0.0

    @abstractmethod
    def submit_order(self, order: BrokerOrder) -> str:
        """Submit an order and return order ID."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        ...

    @abstractmethod
    def get_positions(self) -> List[BrokerPosition]:
        """Get all current positions."""
        ...

    @abstractmethod
    def get_balance(self) -> float:
        """Get account balance."""
        ...

    def get_broker_name(self) -> str:
        return self._broker_name

    def get_order(self, order_id: str) -> Optional[BrokerOrder]:
        return self._orders.get(order_id)

    def get_orders(self, status: Optional[OrderStatus] = None) -> List[BrokerOrder]:
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def initialize(self, config: Dict[str, Any]) -> bool:
        self._config = config
        self._initialized = True
        return True

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> bool:
        self._running = False
        return True

    def health_check(self) -> bool:
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["broker"] = self._broker_name
        status["openOrders"] = sum(
            1 for o in self._orders.values()
            if o.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL)
        )
        status["positions"] = len(self._positions)
        status["balance"] = self._balance
        return status


class BrokerSDK:
    """
    SDK for managing broker adapter plugins.
    """

    def __init__(self):
        self._brokers: Dict[str, BrokerAdapterPlugin] = {}

    def register(self, broker: BrokerAdapterPlugin) -> str:
        name = broker.__class__.__name__
        self._brokers[name] = broker
        return name

    def get_broker(self, name: str) -> Optional[BrokerAdapterPlugin]:
        return self._brokers.get(name)

    def list_brokers(self) -> List[str]:
        return list(self._brokers.keys())

    def submit_order(
        self,
        broker_name: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> Optional[str]:
        broker = self._brokers.get(broker_name)
        if not broker:
            return None
        order = BrokerOrder(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        return broker.submit_order(order)
