"""Suspend Handler — Handles order suspension and resumption.

Processes order suspension (kill switch) and resumption events.
Used for risk control, regulatory halts, and operational pauses.

Pipeline:
    Suspend Request → Transition to SUSPENDED → Monitor → Resume → Back to WORKING

Key features:
- Kill switch integration
- Regulatory halt handling
- Graceful suspension and resumption
- Audit trail for all suspend/resume actions
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

logger = logging.getLogger(__name__)


@dataclass
class SuspendResult:
    """Result of order suspension/resumption."""
    order_id: str
    action: str = ""  # "suspend" or "resume"
    success: bool = False
    reason: str = ""
    source: str = ""
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "action": self.action,
            "success": self.success,
            "reason": self.reason,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class SuspendHandler:
    """Handles order suspension and resumption.

    Suspends active orders for risk control, regulatory halts,
    or operational reasons. Supports graceful resumption back
    to working state.

    Usage::

        handler = SuspendHandler(transition_engine)
        result = await handler.suspend(order, reason="Risk kill switch")
        # ... later ...
        result = await handler.resume(order)
    """

    def __init__(self, transition_engine: TransitionEngine) -> None:
        self._engine = transition_engine
        # Track suspended orders
        self._suspended: dict[str, dict[str, Any]] = {}

    async def suspend(
        self,
        order: Order,
        reason: str = "",
        source: str = "RISK",
        suspend_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> SuspendResult:
        """Suspend an active order.

        Args:
            order: Order to suspend
            reason: Reason for suspension
            source: Source of suspension (RISK, MANUAL, REGULATORY)
            suspend_id: Unique suspend event ID
            payload: Additional suspend data

        Returns:
            SuspendResult with suspension status
        """
        current_status = LifecycleStatus(order.status.value)

        if not current_status.is_active and current_status != LifecycleStatus.SUSPENDED:
            return SuspendResult(
                order_id=order.order_id,
                action="suspend",
                success=False,
                reason=f"Cannot suspend order in {current_status.value} state",
                source=source,
            )

        if current_status == LifecycleStatus.SUSPENDED:
            return SuspendResult(
                order_id=order.order_id,
                action="suspend",
                success=False,
                reason="Order is already suspended",
                source=source,
            )

        # Save pre-suspension state
        self._suspended[order.order_id] = {
            "previous_status": current_status.value,
            "suspended_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "source": source,
        }

        # Execute SUSPEND transition
        event = TransitionEvent(
            event_id=suspend_id or f"suspend-{order.order_id}",
            order_id=order.order_id,
            event_type=TransitionEventType.SUSPEND,
            from_status=current_status,
            to_status=LifecycleStatus.SUSPENDED,
            payload=payload or {"reason": reason, "source": source},
        )

        transition_result = await self._engine.transition(order, event)

        logger.warning(
            f"Order {order.order_id} SUSPENDED by {source}: "
            f"reason='{reason}'"
        )

        return SuspendResult(
            order_id=order.order_id,
            action="suspend",
            success=True,
            reason=reason or "Suspended",
            source=source,
            transition=transition_result,
        )

    async def resume(
        self,
        order: Order,
        resume_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> SuspendResult:
        """Resume a suspended order.

        Args:
            order: Suspended order to resume
            resume_id: Unique resume event ID
            payload: Additional resume data

        Returns:
            SuspendResult with resumption status
        """
        current_status = LifecycleStatus(order.status.value)

        if current_status != LifecycleStatus.SUSPENDED:
            return SuspendResult(
                order_id=order.order_id,
                action="resume",
                success=False,
                reason=f"Cannot resume order in {current_status.value} state",
            )

        # Determine target status based on fill state
        if order.filled_quantity > 0:
            target_status = LifecycleStatus.PARTIALLY_FILLED
        else:
            target_status = LifecycleStatus.WORKING

        # Execute RESUME transition (to WORKING)
        event = TransitionEvent(
            event_id=resume_id or f"resume-{order.order_id}",
            order_id=order.order_id,
            event_type=TransitionEventType.RESUME,
            from_status=current_status,
            to_status=target_status,
            payload=payload or {},
        )

        transition_result = await self._engine.transition(order, event)

        # Clean up suspension tracking
        self._suspended.pop(order.order_id, None)

        logger.info(f"Order {order.order_id} RESUMED to {target_status.value}")

        return SuspendResult(
            order_id=order.order_id,
            action="resume",
            success=True,
            reason=f"Resumed to {target_status.value}",
            transition=transition_result,
        )

    def is_suspended(self, order_id: str) -> bool:
        """Check if an order is suspended.

        Args:
            order_id: Order identifier

        Returns:
            True if the order is currently suspended
        """
        return order_id in self._suspended

    def get_suspension_info(self, order_id: str) -> Optional[dict[str, Any]]:
        """Get suspension details for an order.

        Args:
            order_id: Order identifier

        Returns:
            Suspension details or None
        """
        return self._suspended.get(order_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suspended_orders": len(self._suspended),
            "suspensions": dict(self._suspended),
        }
