"""Broker Gateway — abstract broker connection layer.

Provides a unified interface for connecting to various brokers:
- US Broker (Interactive Brokers, Alpaca, etc.)
- HK Broker (Futu, etc.)
- Futures Broker (CTP, etc.)
- FX Broker (OANDA, etc.)

Each broker implementation extends BrokerGateway and provides
market-specific connection, order submission, and query logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class BrokerType(str, Enum):
    """Supported broker types."""

    US_STOCK = "US_STOCK"
    HK_STOCK = "HK_STOCK"
    FUTURES = "FUTURES"
    FX = "FX"
    PAPER = "PAPER"  # Simulated/paper trading


class ConnectionStatus(str, Enum):
    """Broker connection status."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class OrderAction(str, Enum):
    """Broker-level order action."""

    NEW = "NEW"
    CANCEL = "CANCEL"
    REPLACE = "REPLACE"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class BrokerOrderRequest:
    """Order request sent to a broker."""

    symbol: str
    side: str          # "BUY" or "SELL"
    quantity: float
    price: float = 0.0
    order_type: str = "MARKET"
    time_in_force: str = "DAY"
    account_id: str = ""
    client_order_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerOrderResponse:
    """Response from a broker after order submission."""

    broker_order_id: str
    client_order_id: str
    status: str
    filled_quantity: float = 0.0
    average_price: float = 0.0
    commission: float = 0.0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BrokerPosition:
    """Position information from a broker."""

    symbol: str
    quantity: float
    average_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    currency: str = "USD"


@dataclass
class BrokerBalance:
    """Account balance information from a broker."""

    account_id: str
    currency: str = "USD"
    total_cash: float = 0.0
    available_cash: float = 0.0
    buying_power: float = 0.0
    margin_used: float = 0.0
    total_equity: float = 0.0


# =============================================================================
# Abstract Broker Gateway
# =============================================================================


class BrokerGateway(ABC):
    """Abstract base class for all broker connections.

    Defines the standard interface that every broker implementation
    must provide. This enables the OMS to work with any broker
    through a uniform API.

    Subclasses:
        InteractiveBrokersGateway, FutuGateway, CTPGateway,
        OANDAGateway, PaperTradingGateway
    """

    def __init__(self, broker_type: BrokerType, name: str = "") -> None:
        self.broker_type = broker_type
        self.name = name or broker_type.value
        self._connection_status = ConnectionStatus.DISCONNECTED

    @property
    def connection_status(self) -> ConnectionStatus:
        """Current connection status."""
        return self._connection_status

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def connect(self, **credentials) -> bool:
        """Establish connection to the broker.

        Args:
            **credentials: Broker-specific authentication params

        Returns:
            True if connected successfully
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the broker."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if currently connected to the broker.

        Returns:
            True if connected
        """
        ...

    # -------------------------------------------------------------------------
    # Order Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    async def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        """Submit an order to the broker.

        Args:
            request: Standardized order request

        Returns:
            Broker response with order ID and status
        """
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str, reason: str = "") -> BrokerOrderResponse:
        """Cancel an existing order at the broker.

        Args:
            broker_order_id: Broker's order identifier
            reason: Reason for cancellation

        Returns:
            Broker response confirming cancellation
        """
        ...

    @abstractmethod
    async def replace_order(
        self,
        broker_order_id: str,
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None,
    ) -> BrokerOrderResponse:
        """Replace (modify) an existing order at the broker.

        Args:
            broker_order_id: Broker's order identifier
            new_quantity: New order quantity
            new_price: New limit price

        Returns:
            Broker response confirming modification
        """
        ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> BrokerOrderResponse:
        """Query the current status of an order at the broker.

        Args:
            broker_order_id: Broker's order identifier

        Returns:
            Current order status from broker
        """
        ...

    # -------------------------------------------------------------------------
    # Account & Position Queries
    # -------------------------------------------------------------------------

    @abstractmethod
    async def query_positions(self, account_id: str = "") -> List[BrokerPosition]:
        """Query current positions.

        Args:
            account_id: Account to query (default account if empty)

        Returns:
            List of current positions
        """
        ...

    @abstractmethod
    async def query_balance(self, account_id: str = "") -> BrokerBalance:
        """Query account balance and buying power.

        Args:
            account_id: Account to query (default account if empty)

        Returns:
            Account balance information
        """
        ...

    # -------------------------------------------------------------------------
    # Market Data
    # -------------------------------------------------------------------------

    @abstractmethod
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get current market data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Market data including bid, ask, last price, volume
        """
        ...


# =============================================================================
# Concrete Gateway Implementations
# =============================================================================


class PaperTradingGateway(BrokerGateway):
    """Simulated broker for paper trading and backtesting.

    All orders are filled immediately at the last price.
    No real money is used.
    """

    def __init__(self, initial_balance: float = 1_000_000.0, name: str = "PaperBroker") -> None:
        super().__init__(BrokerType.PAPER, name)
        self._connected = False
        self._orders: Dict[str, BrokerOrderResponse] = {}
        self._positions: Dict[str, BrokerPosition] = {}
        self._balance = BrokerBalance(
            account_id="PAPER_001",
            total_cash=initial_balance,
            available_cash=initial_balance,
            buying_power=initial_balance * 2,
            total_equity=initial_balance,
        )
        self._counter = 0

    async def connect(self, **credentials) -> bool:
        self._connected = True
        self._connection_status = ConnectionStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self._connection_status = ConnectionStatus.DISCONNECTED

    async def is_connected(self) -> bool:
        return self._connected

    async def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        if not self._connected:
            raise ConnectionError("Not connected to broker")

        self._counter += 1
        broker_order_id = f"BRK_{self._counter:08d}"

        # Simulate immediate fill for market orders
        fill_qty = request.quantity
        avg_price = request.price if request.price > 0 else 100.0

        # Update position
        pos = self._positions.get(request.symbol)
        if pos is None:
            pos = BrokerPosition(symbol=request.symbol, quantity=0.0, average_cost=0.0)
            self._positions[request.symbol] = pos

        if request.side == "BUY":
            total_cost = fill_qty * avg_price
            new_qty = pos.quantity + fill_qty
            pos.average_cost = ((pos.quantity * pos.average_cost) + total_cost) / new_qty if new_qty else 0
            pos.quantity = new_qty
        else:
            pos.quantity -= fill_qty
            if pos.quantity == 0:
                pos.average_cost = 0.0

        response = BrokerOrderResponse(
            broker_order_id=broker_order_id,
            client_order_id=request.client_order_id,
            status="FILLED",
            filled_quantity=fill_qty,
            average_price=avg_price,
        )
        self._orders[broker_order_id] = response
        return response

    async def cancel_order(self, broker_order_id: str, reason: str = "") -> BrokerOrderResponse:
        response = self._orders.get(broker_order_id)
        if response is None:
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                client_order_id="",
                status="ERROR",
                message="Order not found",
            )
        response.status = "CANCELLED"
        response.message = reason
        return response

    async def replace_order(
        self,
        broker_order_id: str,
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None,
    ) -> BrokerOrderResponse:
        response = self._orders.get(broker_order_id)
        if response is None:
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                client_order_id="",
                status="ERROR",
                message="Order not found",
            )
        # Cancel and re-submit
        response.status = "REPLACED"
        if new_quantity:
            response.filled_quantity = new_quantity
        if new_price:
            response.average_price = new_price
        return response

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderResponse:
        response = self._orders.get(broker_order_id)
        if response is None:
            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                client_order_id="",
                status="UNKNOWN",
                message="Order not found",
            )
        return response

    async def query_positions(self, account_id: str = "") -> List[BrokerPosition]:
        return list(self._positions.values())

    async def query_balance(self, account_id: str = "") -> BrokerBalance:
        return self._balance

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "bid": 100.0,
            "ask": 100.01,
            "last_price": 100.0,
            "volume": 1_000_000,
            "timestamp": datetime.utcnow().isoformat(),
        }
