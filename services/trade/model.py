"""
Trade domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class Trade:
    order_id: UUID
    account_id: str
    symbol: str
    quantity: Decimal
    price: Decimal

    trade_id: UUID = field(default_factory=uuid4)
    execution_id: str | None = None
    liquidity: str = "UNKNOWN"
    commission: Decimal = Decimal("0")
    executed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )