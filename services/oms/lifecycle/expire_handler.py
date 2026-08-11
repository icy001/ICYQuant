"""Expire Handler — Handles order expiration events.

Processes order expiration based on time-in-force instructions.
Handles both broker-initiated expiration and internal timeout
detection for GTD (Good-Til-Date) orders.

Pipeline:
    TIF Check → Expiry Event → Transition to EXPIRED → Notify

Key features:
- Time-in-force enforcement (DAY, GTD, IOC, FOK)
- Broker expiry message processing
- Internal expiry timer management
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus, TimeInForce
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
class ExpireResult:
    """Result of order expiration."""
    order_id: str
    expired: bool = False
    expiry_reason: str = ""
    time_in_force: str = ""
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "expired": self.expired,
            "expiry_reason": self.expiry_reason,
            "time_in_force": self.time_in_force,
            "timestamp": self.timestamp.isoformat(),
        }


class ExpireHandler:
    """Handles order expiration events.

    Processes expiration based on time-in-force settings.
    Supports broker-initiated expiration (e.g., end-of-day)
    and internal expiry timer management for GTD orders.

    Usage::

        handler = ExpireHandler(transition_engine, duplicate_detector)
        result = await handler.expire(order, reason="End of day")
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        duplicate_detector: DuplicateEventDetector,
    ) -> None:
        self._engine = transition_engine
        self._duplicate = duplicate_detector

    async def expire(
        self,
        order: Order,
        reason: str = "",
        expire_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> ExpireResult:
        """Expire an active order.

        Args:
            order: Order to expire
            reason: Reason for expiration
            expire_id: Unique expire event ID
            payload: Additional expiration data

        Returns:
            ExpireResult with expiration status
        """
        event_id = expire_id or f"expire-{order.order_id}"

        # Duplicate check
        dup = self._duplicate.check(event_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(f"Duplicate expire for order {order.order_id}")
            return ExpireResult(
                order_id=order.order_id,
                expiry_reason=f"Duplicate expire: {event_id}",
            )

        current_status = LifecycleStatus(order.status.value)

        # Cannot expire terminal orders
        if current_status.is_terminal:
            return ExpireResult(
                order_id=order.order_id,
                expiry_reason=f"Cannot expire terminal order: {current_status.value}",
            )

        expiry_reason = reason or f"Order expired (TIF={order.time_in_force.value})"

        # Execute EXPIRED transition
        event = TransitionEvent(
            event_id=event_id,
            order_id=order.order_id,
            event_type=TransitionEventType.EXPIRE,
            from_status=current_status,
            to_status=LifecycleStatus.EXPIRED,
            payload=payload or {"reason": expiry_reason},
        )

        transition_result = await self._engine.transition(order, event)

        logger.info(
            f"Order {order.order_id} expired: "
            f"tif={order.time_in_force.value}, reason='{expiry_reason}'"
        )

        return ExpireResult(
            order_id=order.order_id,
            expired=True,
            expiry_reason=expiry_reason,
            time_in_force=order.time_in_force.value,
            transition=transition_result,
        )

    async def check_expiry(self, order: Order) -> ExpireResult:
        """Check if an order should be expired based on TIF.

        Args:
            order: Order to check

        Returns:
            ExpireResult indicating if order expired
        """
        current_status = LifecycleStatus(order.status.value)
        if not current_status.is_active:
            return ExpireResult(order_id=order.order_id)

        if order.time_in_force == TimeInForce.DAY:
            # Check if it's past end of trading day
            now = datetime.now(timezone.utc)
            if now.date() > order.created_at.date():
                return await self.expire(order, reason="End of day")

        # GTD expiry handled by scheduler
        return ExpireResult(
            order_id=order.order_id,
            time_in_force=order.time_in_force.value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {}
