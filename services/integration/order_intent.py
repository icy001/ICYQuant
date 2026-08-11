"""OrderIntent — governance object representing an intended order before admission.

An OrderIntent is NOT an Order. It is the governance envelope that carries
all upstream context (risk, governance, authority, approval) into the
Admission Boundary. Only after passing all admission checks does it produce
a real Order + Certificate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class Side(Enum):
    """Order side."""
    BUY = auto()
    SELL = auto()

    @property
    def label(self) -> str:
        _labels = {Side.BUY: "BUY", Side.SELL: "SELL"}
        return _labels.get(self, "UNKNOWN")


class OrderType(Enum):
    """Order type."""
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()

    @property
    def label(self) -> str:
        _labels = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.STOP: "STOP",
            OrderType.STOP_LIMIT: "STOP_LIMIT",
        }
        return _labels.get(self, "UNKNOWN")


class TimeInForce(Enum):
    """Time in force."""
    DAY = auto()
    GTC = auto()
    IOC = auto()
    FOK = auto()

    @property
    def label(self) -> str:
        _labels = {
            TimeInForce.DAY: "DAY",
            TimeInForce.GTC: "GTC",
            TimeInForce.IOC: "IOC",
            TimeInForce.FOK: "FOK",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class OrderIntent:
    """Governance-level order intent.

    Carries full upstream context through the admission boundary.
    Distinguished from a raw Order: this is the auditable, governable
    representation of what the user/system intends to trade.
    """

    intent_id: str = field(
        default_factory=lambda: f"INTENT-{uuid.uuid4().hex[:12].upper()}"
    )
    flow_id: str = ""
    decision_id: str = ""
    strategy_id: str = ""
    portfolio_id: str = ""
    account_id: str = ""

    symbol: str = ""
    side: Side = Side.BUY
    quantity: float = 0.0
    order_type: OrderType = OrderType.LIMIT
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    currency: str = "USD"
    venue: str = ""

    risk_context: Optional[Dict[str, Any]] = None
    governance_context: Optional[Dict[str, Any]] = None
    authority_context: Optional[Dict[str, Any]] = None
    approval_context: Optional[Dict[str, Any]] = None

    created_at: float = field(default_factory=lambda: __import__("time").time())

    def with_flow_id(self, flow_id: str) -> "OrderIntent":
        self.flow_id = flow_id
        return self

    def with_decision_id(self, decision_id: str) -> "OrderIntent":
        self.decision_id = decision_id
        return self

    def with_strategy_id(self, strategy_id: str) -> "OrderIntent":
        self.strategy_id = strategy_id
        return self

    def with_portfolio_id(self, portfolio_id: str) -> "OrderIntent":
        self.portfolio_id = portfolio_id
        return self

    def with_account_id(self, account_id: str) -> "OrderIntent":
        self.account_id = account_id
        return self

    def with_symbol(self, symbol: str) -> "OrderIntent":
        self.symbol = symbol
        return self

    def with_side(self, side: Side) -> "OrderIntent":
        self.side = side
        return self

    def with_quantity(self, quantity: float) -> "OrderIntent":
        self.quantity = quantity
        return self

    def with_order_type(self, order_type: OrderType) -> "OrderIntent":
        self.order_type = order_type
        return self

    def with_limit_price(self, limit_price: float) -> "OrderIntent":
        self.limit_price = limit_price
        return self

    def with_venue(self, venue: str) -> "OrderIntent":
        self.venue = venue
        return self

    def with_risk_context(self, ctx: Dict[str, Any]) -> "OrderIntent":
        self.risk_context = ctx
        return self

    def with_governance_context(self, ctx: Dict[str, Any]) -> "OrderIntent":
        self.governance_context = ctx
        return self

    def with_authority_context(self, ctx: Dict[str, Any]) -> "OrderIntent":
        self.authority_context = ctx
        return self

    def with_approval_context(self, ctx: Dict[str, Any]) -> "OrderIntent":
        self.approval_context = ctx
        return self

    @property
    def notional(self) -> float:
        """Estimate notional value."""
        if self.limit_price and self.limit_price > 0:
            return self.quantity * self.limit_price
        return 0.0

    @property
    def is_valid(self) -> bool:
        """Basic structural validity check."""
        return bool(
            self.flow_id
            and self.symbol
            and self.quantity > 0
            and self.side in (Side.BUY, Side.SELL)
            and self.account_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "side": self.side.name,
            "quantity": self.quantity,
            "order_type": self.order_type.name,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.name,
            "currency": self.currency,
            "venue": self.venue,
            "risk_context": self.risk_context,
            "governance_context": self.governance_context,
            "authority_context": self.authority_context,
            "approval_context": self.approval_context,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"OrderIntent(intent_id={self.intent_id}, flow_id={self.flow_id}, "
            f"symbol={self.symbol}, side={self.side.name}, "
            f"quantity={self.quantity}, order_type={self.order_type.name})"
        )
