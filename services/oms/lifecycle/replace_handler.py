"""Replace Handler — Handles order modification (amend/replace) requests.

Processes order modification requests for working orders. Supports
price and quantity changes while preserving version history.

Pipeline:
    Working Order → Modify Price/Qty → New Version → Replace ACK

Key features:
- Price and quantity modification
- Version tracking with history
- Quantity increase/decrease validation
- Preserves fill state through modifications
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
class ReplaceResult:
    """Result of an order modification."""
    order_id: str
    success: bool = False
    new_price: Optional[float] = None
    new_quantity: Optional[float] = None
    old_price: float = 0.0
    old_quantity: float = 0.0
    version: int = 0
    reason: str = ""
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def price_changed(self) -> bool:
        """Whether the price was changed."""
        return self.new_price is not None and self.new_price != self.old_price

    @property
    def quantity_changed(self) -> bool:
        """Whether the quantity was changed."""
        return self.new_quantity is not None and self.new_quantity != self.old_quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "new_price": self.new_price,
            "new_quantity": self.new_quantity,
            "old_price": self.old_price,
            "old_quantity": self.old_quantity,
            "version": self.version,
            "price_changed": self.price_changed,
            "quantity_changed": self.quantity_changed,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class ReplaceHandler:
    """Handles order modification (replace/amend) requests.

    Modifies working orders with new price or quantity parameters.
    Tracks version history and validates modifications against
    current order state.

    All replacements preserve the historical version of the order.

    Usage::

        handler = ReplaceHandler(transition_engine)
        result = await handler.replace(
            order, new_price=152.50, new_quantity=500
        )
    """

    def __init__(self, transition_engine: TransitionEngine) -> None:
        self._engine = transition_engine
        # order_id → version counter
        self._versions: dict[str, int] = {}
        # order_id → list of historical versions
        self._history: dict[str, list[dict[str, Any]]] = {}

    async def replace(
        self,
        order: Order,
        new_price: Optional[float] = None,
        new_quantity: Optional[float] = None,
        replace_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> ReplaceResult:
        """Modify a working order.

        Args:
            order: Working order to modify
            new_price: New limit price (None to keep current)
            new_quantity: New quantity (None to keep current)
            replace_id: Unique replace event ID
            payload: Additional replace data

        Returns:
            ReplaceResult with modification details

        Raises:
            ValueError: If order is not in a modifiable state
        """
        current_status = LifecycleStatus(order.status.value)

        # Validate modifiable state
        if current_status not in (
            LifecycleStatus.WORKING,
            LifecycleStatus.PARTIALLY_FILLED,
        ):
            return ReplaceResult(
                order_id=order.order_id,
                success=False,
                reason=f"Cannot modify order in {current_status.value} state",
            )

        # Validate quantity against filled quantity
        if new_quantity is not None and new_quantity < order.filled_quantity:
            return ReplaceResult(
                order_id=order.order_id,
                success=False,
                reason=f"New quantity {new_quantity} is less than filled quantity {order.filled_quantity}",
            )

        old_price = order.price
        old_quantity = order.quantity

        # Track version history
        self._versions[order.order_id] = self._versions.get(order.order_id, 0) + 1
        version = self._versions[order.order_id]

        # Save historical version
        history_entry = {
            "version": version,
            "price": old_price,
            "quantity": old_quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if order.order_id not in self._history:
            self._history[order.order_id] = []
        self._history[order.order_id].append(history_entry)

        # Apply modifications
        if new_price is not None:
            order.price = new_price
        if new_quantity is not None:
            order.quantity = new_quantity

        # Execute REPLACED transition
        event = TransitionEvent(
            event_id=replace_id or f"replace-{order.order_id}-v{version}",
            order_id=order.order_id,
            event_type=TransitionEventType.REPLACE,
            from_status=current_status,
            to_status=LifecycleStatus.REPLACED,
            payload=payload or {
                "version": version,
                "old_price": old_price,
                "new_price": order.price,
                "old_quantity": old_quantity,
                "new_quantity": order.quantity,
            },
        )

        transition_result = await self._engine.transition(order, event)

        logger.info(
            f"Order {order.order_id} replaced (v{version}): "
            f"price: {old_price} → {order.price}, "
            f"qty: {old_quantity} → {order.quantity}"
        )

        return ReplaceResult(
            order_id=order.order_id,
            success=True,
            new_price=order.price,
            new_quantity=order.quantity,
            old_price=old_price,
            old_quantity=old_quantity,
            version=version,
            reason=f"Replaced to v{version}",
            transition=transition_result,
        )

    def get_history(self, order_id: str) -> list[dict[str, Any]]:
        """Get modification history for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of historical version entries
        """
        return self._history.get(order_id, [])

    def get_version(self, order_id: str) -> int:
        """Get current version number for an order.

        Args:
            order_id: Order identifier

        Returns:
            Current version number
        """
        return self._versions.get(order_id, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_versions": {
                oid: v for oid, v in self._versions.items()
            },
        }
