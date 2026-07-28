"""Execution Order Model – core order representation for the execution pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    ROUTING = "routing"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class ExecutionOrder:
    """Represents a single order to be executed.

    Carries all information needed for the execution intelligence
    pipeline: symbol, direction, quantity, constraints, and metadata
    from upstream portfolio decisions.
    """

    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int

    # Optional constraints
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    urgency: str = "normal"  # "low", "normal", "high", "critical"

    # Metadata
    portfolio_id: str = ""
    strategy_id: str = ""
    reason: str = ""
    parent_order_id: str = ""

    # Status tracking
    status: str = "pending"
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    slippage_bps: float = 0.0

    def notional_value(self, reference_price: float) -> float:
        """Compute notional value at a given reference price."""
        return self.quantity * reference_price

    def fill_rate(self) -> float:
        """Return the fill progress (0.0 - 1.0)."""
        if self.quantity <= 0:
            return 0.0
        return min(self.filled_quantity / self.quantity, 1.0)

    def is_complete(self) -> bool:
        return self.status in ("filled", "cancelled", "rejected")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "urgency": self.urgency,
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "reason": self.reason,
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "slippage_bps": self.slippage_bps,
        }
