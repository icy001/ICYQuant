"""Multi-Account Adapter Layer - unified Account / Broker domain models.

The adapter layer is the only place that knows about broker specifics.
Strategies, the Risk Engine and the Order Domain only ever see OrderIntent
and the unified Account model below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set


# ---------------------------------------------------------------------------
# Market & capability constants
# ---------------------------------------------------------------------------


class Market:
    """Supported market types."""

    CN_STOCK = "CN_STOCK"
    CN_FUTURES = "CN_FUTURES"
    US_EQUITY = "US_EQUITY"
    FX = "FX"


MARKET_LABELS = {
    Market.CN_STOCK: "A-Share",
    Market.CN_FUTURES: "Futures",
    Market.US_EQUITY: "US Equity",
    Market.FX: "FX",
}


class AccountStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DISABLED = "DISABLED"


class ConnectionStatus:
    CONNECTED = "CONNECTED"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class OrderStatus:
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Capability:
    """Adapter capabilities - different markets support different features."""

    SUBMIT_ORDER = "submit_order"
    CANCEL_ORDER = "cancel_order"
    QUERY_ORDER = "query_order"
    POSITIONS = "positions"
    EXECUTIONS = "executions"
    ACCOUNT_BALANCE = "account_balance"
    BUYING_POWER = "buying_power"
    MARGIN = "margin"
    SETTLEMENT = "settlement"
    LEVERAGE = "leverage"
    SWAP = "swap"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """A single market position on an account."""

    account_id: str
    symbol: str
    market: str
    side: str  # BUY / SELL
    quantity: float
    average_price: float
    last_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    exposure: float = 0.0
    currency: str = "USD"
    margin: Optional[float] = None  # margin consumed (futures / FX)

    def __post_init__(self) -> None:
        self.quantity = float(self.quantity)
        self.average_price = float(self.average_price)
        self.last_price = float(self.last_price)
        if not self.market_value:
            self.market_value = round(self.quantity * self.last_price, 2)
        if not self.unrealized_pnl:
            self.unrealized_pnl = round(
                (self.last_price - self.average_price) * self.quantity, 2
            )
        if not self.exposure:
            self.exposure = round(self.quantity * self.last_price, 2)


@dataclass
class OrderRecord:
    """A broker-side order returned by an adapter."""

    order_id: str
    account_id: str
    broker_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str = OrderStatus.CREATED
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    strategy_id: str = ""
    market: str = ""
    rejection_reason: str = ""


@dataclass
class ExecutionRecord:
    """A broker-side execution (fill) returned by an adapter."""

    execution_id: str
    order_id: str
    account_id: str
    broker_id: str
    symbol: str
    side: str
    fill_quantity: float
    fill_price: float
    slippage: float = 0.0
    timestamp: str = ""
    market: str = ""


@dataclass
class AccountBalance:
    """Unified account balance snapshot."""

    account_id: str
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    margin: float = 0.0
    currency: str = "USD"
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    drawdown: float = 0.0


@dataclass
class Account:
    """Unified account model (the Account Domain).

    ``equity`` / ``cash`` / ``buying_power`` / ``margin`` are the live
    snapshot refreshed by ``sync_account``; ``positions`` / ``orders`` /
    ``executions`` are the cached broker state used by the Dashboard.
    """

    account_id: str
    broker_id: str
    broker_name: str
    market: str
    currency: str
    status: str = AccountStatus.ACTIVE
    name: str = ""
    capabilities: Set[str] = field(default_factory=set)
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    margin: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    drawdown: float = 0.0
    positions: List[Position] = field(default_factory=list)
    orders: List[OrderRecord] = field(default_factory=list)
    executions: List[ExecutionRecord] = field(default_factory=list)


@dataclass
class Broker:
    """A broker that owns one or more accounts."""

    broker_id: str
    broker_name: str
    market: str
    adapter_type: str
    connection_status: str = ConnectionStatus.DISCONNECTED
    capabilities: Set[str] = field(default_factory=set)
    account_ids: List[str] = field(default_factory=list)


@dataclass
class OrderIntent:
    """What a strategy wants to do - the only order input the adapter
    layer needs. The router decides which account actually receives it."""

    strategy_id: str
    symbol: str
    market: str
    side: str  # BUY / SELL
    quantity: float
    price: float
    account_id: Optional[str] = None  # explicit target (routing hint)
