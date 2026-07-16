"""
Execution report model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .events import OrderTransition


@dataclass(frozen=True)
class ExecutionReport:
    order_id: UUID
    transition: OrderTransition
    filled_quantity: Decimal = Decimal("0")
    average_price: Decimal = Decimal("0")