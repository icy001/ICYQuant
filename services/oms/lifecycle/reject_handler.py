"""Reject Handler — Handles order rejection events.

Processes rejection messages from brokers and exchanges. Records
rejection reasons and transitions orders to REJECTED state.

Pipeline:
    Reject Event → Record Reason → Transition to REJECTED → Notify Strategy

Key features:
- Rejection reason capture
- Broker/exchange error code mapping
- Strategy notification on rejection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import (
    TransitionEngine,
    TransitionEvent,
    TransitionEventType,
    TransitionResult,
)
from services.oms.lifecycle.duplicate_event_detector import DuplicateEventDetector

logger = logging.getLogger(__name__)


@dataclass
class RejectResult:
    """Result of an order rejection."""
    order_id: str
    success: bool = False
    rejection_reason: str = ""
    rejection_code: str = ""
    source: str = ""
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "rejection_reason": self.rejection_reason,
            "rejection_code": self.rejection_code,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class RejectHandler:
    """Handles order rejection events.

    Processes rejections from broker gateways and exchanges.
    Records detailed rejection reasons and codes for analysis.

    Usage::

        handler = RejectHandler(transition_engine, duplicate_detector)
        result = await handler.reject(
            order,
            reason="Invalid symbol",
            rejection_code="ERR_SYMBOL",
            source="BROKER",
        )
    """

    # Common rejection codes
    REJECTION_CODES: dict[str, str] = {
        "ERR_SYMBOL": "Invalid or unknown symbol",
        "ERR_PRICE": "Price out of allowed range",
        "ERR_QTY": "Quantity invalid",
        "ERR_ORDER_TYPE": "Unsupported order type",
        "ERR_MARGIN": "Insufficient margin",
        "ERR_RISK": "Blocked by risk controls",
        "ERR_MARKET_CLOSED": "Market is closed",
        "ERR_HALTED": "Symbol is halted",
        "ERR_DUPLICATE": "Duplicate order detected",
        "ERR_LIMIT": "Order limit exceeded",
        "ERR_SYSTEM": "System error",
    }

    def __init__(
        self,
        transition_engine: TransitionEngine,
        duplicate_detector: DuplicateEventDetector,
    ) -> None:
        self._engine = transition_engine
        self._duplicate = duplicate_detector

    async def reject(
        self,
        order: Order,
        reason: str = "",
        rejection_code: str = "",
        source: str = "BROKER",
        reject_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> RejectResult:
        """Process an order rejection.

        Args:
            order: Order to reject
            reason: Human-readable rejection reason
            rejection_code: Machine-readable rejection code
            source: Source of rejection (BROKER, EXCHANGE, OMS, RISK)
            reject_id: Unique reject event ID
            payload: Additional rejection data

        Returns:
            RejectResult with rejection details
        """
        event_id = reject_id or f"reject-{order.order_id}"

        # Duplicate check
        dup = self._duplicate.check(event_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(f"Duplicate reject for order {order.order_id}")
            return RejectResult(
                order_id=order.order_id,
                success=False,
                rejection_reason=f"Duplicate reject: {event_id}",
            )

        current_status = LifecycleStatus(order.status.value)

        # Cannot reject terminal orders
        if current_status.is_terminal:
            return RejectResult(
                order_id=order.order_id,
                success=False,
                rejection_reason=f"Order already in terminal state: {current_status.value}",
            )

        # Resolve full rejection reason
        full_reason = reason
        if rejection_code and rejection_code in self.REJECTION_CODES:
            full_reason = f"[{rejection_code}] {self.REJECTION_CODES[rejection_code]}"
            if reason:
                full_reason = f"{full_reason} - {reason}"

        # Update order
        order.rejection_reason = full_reason

        # Execute REJECTED transition
        event = TransitionEvent(
            event_id=event_id,
            order_id=order.order_id,
            event_type=TransitionEventType.REJECT,
            from_status=current_status,
            to_status=LifecycleStatus.REJECTED,
            payload=payload or {
                "reason": full_reason,
                "rejection_code": rejection_code,
                "source": source,
            },
        )

        transition_result = await self._engine.transition(order, event)

        logger.warning(
            f"Order {order.order_id} rejected by {source}: "
            f"code={rejection_code}, reason='{full_reason}'"
        )

        return RejectResult(
            order_id=order.order_id,
            success=True,
            rejection_reason=full_reason,
            rejection_code=rejection_code,
            source=source,
            transition=transition_result,
        )

    def get_rejection_description(self, code: str) -> str:
        """Get human-readable description for a rejection code.

        Args:
            code: Rejection code

        Returns:
            Human-readable description
        """
        return self.REJECTION_CODES.get(code, f"Unknown error: {code}")
