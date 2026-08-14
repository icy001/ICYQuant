from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionRequestStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ExecutionSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExecutionOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    order_id: str

    symbol: str

    side: ExecutionSide
    order_type: ExecutionOrderType

    quantity: float

    price: float | None = None
    stop_price: float | None = None

    strategy_id: str | None = None

    status: ExecutionRequestStatus = (
        ExecutionRequestStatus.CREATED
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")

        if not self.order_id:
            raise ValueError("order_id is required")

        if not self.symbol:
            raise ValueError("symbol is required")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

        if (
            self.order_type
            in {
                ExecutionOrderType.LIMIT,
                ExecutionOrderType.STOP_LIMIT,
            }
            and self.price is None
        ):
            raise ValueError(
                "price is required for limit orders"
            )

        if (
            self.order_type
            in {
                ExecutionOrderType.STOP,
                ExecutionOrderType.STOP_LIMIT,
            }
            and self.stop_price is None
        ):
            raise ValueError(
                "stop_price is required for stop orders"
            )
