"""
Pre-Trade Risk Request — Standardized order intent model.

Represents an incoming order intent before it reaches OMS. Every
field is immutable once created to ensure traceability through
the risk evaluation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class OrderSide(str, Enum):
    """Order direction."""
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"


class OrderType(str, Enum):
    """Order type classification."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"


class InstrumentType(str, Enum):
    """Financial instrument classification."""
    EQUITY = "equity"
    ETF = "etf"
    FUTURE = "future"
    OPTION = "option"
    FOREX = "forex"
    CRYPTO = "crypto"
    BOND = "bond"
    CFD = "cfd"
    WARRANT = "warrant"
    INDEX = "index"


@dataclass(frozen=True)
class RiskRequest:
    """
    Immutable pre-trade risk evaluation request.

    Represents a single order intent submitted for risk evaluation.
    Contains all information needed by checkers to make a decision.

    Usage::

        req = RiskRequest(
            account_id="ACC-001",
            strategy_id="STRAT-ALPHA",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=500,
            price=150.25,
            instrument_type=InstrumentType.EQUITY,
        )
    """

    # ---- Identifiers ----
    request_id: str = field(default_factory=lambda: uuid4().hex)
    account_id: str = ""
    strategy_id: str = ""
    portfolio_id: Optional[str] = None
    symbol: str = ""
    exchange: Optional[str] = None

    # ---- Order Details ----
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    instrument_type: InstrumentType = InstrumentType.EQUITY

    # ---- Context ----
    account_positions: dict[str, Any] = field(default_factory=dict)
    account_balances: dict[str, Any] = field(default_factory=dict)
    market_data: dict[str, Any] = field(default_factory=dict)
    risk_profile_id: Optional[str] = None

    # ---- Metadata ----
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def notional_value(self) -> float:
        """Estimated notional value of the order."""
        if self.order_type == OrderType.MARKET:
            return self.quantity * (self.market_data.get("last_price", 0.0) or 0.0)
        return self.quantity * (self.price or 0.0)

    @property
    def is_buy(self) -> bool:
        return self.side in (OrderSide.BUY,)

    @property
    def is_sell(self) -> bool:
        return self.side in (OrderSide.SELL, OrderSide.SELL_SHORT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "instrument_type": self.instrument_type.value,
            "notional_value": self.notional_value,
            "created_at": self.created_at.isoformat(),
        }
