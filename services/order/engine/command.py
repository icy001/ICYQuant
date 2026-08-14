"""Order engine commands (Commit 33 Part 1.2).

Every command is a frozen value object carrying only *what to do* and the
metadata needed to trace the action:

* ``correlation_id`` - ties the command to its surrounding workflow
* ``causation_id``   - the id of the message/event that caused this command
* ``timestamp``      - authoritative action time

Trading parameters (symbol / side / quantity / price) are never part of the
commands: they live in the :class:`~services.order.request.normalization.NormalizedOrderRequest`
(single source of truth, Commit 33 Part 1.1 #26) so a request ``BUY 100`` can
never be turned into an order ``SELL 1000`` by a divergent command.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class CreateOrderCommand:
    """Create an order from a HANDOFF order request."""

    order_request_id: str
    client_order_id: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class SubmitOrderCommand:
    """Push the order toward the execution boundary.

    This means *"the engine is asking to send the order"* - it does NOT mean
    the order has been accepted or filled.
    """

    order_id: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class AcceptOrderCommand:
    """Downstream confirms the order was accepted."""

    order_id: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class RejectOrderCommand:
    """Downstream rejected the order; the reason must be recorded."""

    order_id: str
    reason: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class CancelOrderCommand:
    """Request a cancellation.

    A cancel request is NOT a cancellation: the order only becomes CANCELLED
    after the downstream confirms it (ACCEPTED -> CANCEL_PENDING -> CANCELLED).
    """

    order_id: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class ExpireOrderCommand:
    """Expire the order (only legal for orders whose TimeInForce allows it)."""

    order_id: str
    correlation_id: str
    causation_id: Optional[str]
    timestamp: datetime
