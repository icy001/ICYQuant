"""Execution request (Commit 33 Part 1.3).

An :class:`ExecutionRequest` is the *minimal immutable information needed to
send an order to a venue* - it is derived from an
:class:`~services.order.domain.order.Order`, not a copy of it.  It deliberately
carries no lineage fields (strategy / signal / intent / authorization /
certificate / decision): the execution layer may never re-decide or overwrite
the trading intent (Commit 33 Part 1.3 #5).

Every execution attempt has its own ``execution_request_id`` so one order can
legitimately have many execution requests (submit / cancel / retry / query),
with ``causation_id`` keeping the chain ``EXREQ-001 -> EXREQ-002`` (#18-#20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce


@dataclass(frozen=True)
class ExecutionRequest:
    """Minimal immutable payload for one execution attempt."""

    execution_request_id: str

    order_id: str
    client_order_id: str

    symbol: str
    side: OrderSide
    quantity: Decimal

    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Optional[Decimal]

    correlation_id: str
    causation_id: Optional[str]

    timestamp: datetime
