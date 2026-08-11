"""Order aggregate — institutional OMS order."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .order_id import OrderId
from .order_status import OrderStatus
from .order_side import OrderSide
from .order_type import OrderType
from .time_in_force import TimeInForce
from .order_quantity import OrderQuantity
from .order_price import OrderPrice
from .order_lifecycle import (
    OrderLifecycle,
    OrderLifecycleEvent,
    LifecycleEventType,
)


@dataclass
class Order:
    """Institutional OMS Order aggregate.

    An Order is NOT just symbol/side/quantity/price — it carries:
      - Control lineage (flow_id, lineage_id, decision_id, certificate_id)
      - Lifecycle state and event history
      - Quantity lifecycle tracking
      - Version for optimistic concurrency
      - Parent/child order hierarchy

    Orders are created via OrderAcceptor (after certificate verification)
    and managed via OrderLifecycleManager.
    """

    # ── Identity ───────────────────────────────────
    order_id: OrderId = field(default_factory=OrderId)

    # ── Market ─────────────────────────────────────
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY

    # ── Quantity ───────────────────────────────────
    quantity: OrderQuantity = field(default_factory=OrderQuantity)

    # ── Price ──────────────────────────────────────
    price: OrderPrice = field(default_factory=OrderPrice)

    # ── Lifecycle ──────────────────────────────────
    status: OrderStatus = OrderStatus.RECEIVED
    lifecycle: OrderLifecycle = field(default_factory=OrderLifecycle)
    version: int = 0

    # ── Control Lineage ────────────────────────────
    flow_id: str = ""
    lineage_id: str = ""
    decision_id: str = ""
    order_intent_id: str = ""
    certificate_id: str = ""

    # ── Account ────────────────────────────────────
    account_id: str = ""
    strategy_id: str = ""

    # ── Execution ──────────────────────────────────
    execution_status_unknown: bool = False

    # ── Timestamps ─────────────────────────────────
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())
    expires_at: Optional[float] = None

    # ── Metadata ───────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ══════════════════════════════════════════════════
    #  Factory
    # ══════════════════════════════════════════════════

    @classmethod
    def create(cls, **kwargs: Any) -> Order:
        """Create a new Order in RECEIVED state.

        Required kwargs:
            symbol, side, order_type, quantity (float),
            lineage_id (str), certificate_id (str).

        Optional:
            time_in_force, limit_price, stop_price, flow_id,
            decision_id, order_intent_id, account_id, strategy_id,
            client_order_id, parent_order_id, root_order_id,
            expires_at, metadata.
        """
        qty_val = kwargs.pop("quantity", 0.0)
        order_qty = OrderQuantity.for_original(float(qty_val))

        price = OrderPrice(
            limit_price=float(kwargs.pop("limit_price", 0)),
            stop_price=float(kwargs.pop("stop_price", 0)),
        )

        oid_kwargs = {k: kwargs.pop(k, "") for k in
                       ("client_order_id", "parent_order_id", "root_order_id")}
        oid = OrderId(**{k: v for k, v in oid_kwargs.items() if v})

        order = cls(
            order_id=oid,
            symbol=kwargs.pop("symbol", ""),
            side=kwargs.pop("side", OrderSide.BUY),
            order_type=kwargs.pop("order_type", OrderType.MARKET),
            time_in_force=kwargs.pop("time_in_force", TimeInForce.DAY),
            quantity=order_qty,
            price=price,
            lineage_id=kwargs.pop("lineage_id", ""),
            certificate_id=kwargs.pop("certificate_id", ""),
            flow_id=kwargs.pop("flow_id", ""),
            decision_id=kwargs.pop("decision_id", ""),
            order_intent_id=kwargs.pop("order_intent_id", ""),
            account_id=kwargs.pop("account_id", ""),
            strategy_id=kwargs.pop("strategy_id", ""),
            expires_at=kwargs.pop("expires_at", None),
            metadata=kwargs.pop("metadata", {}),
        )

        # Record initial lifecycle event
        order.lifecycle.order_id = order.order_id.order_id
        event = OrderLifecycleEvent.create(
            event_type=LifecycleEventType.ORDER_RECEIVED,
            order_id=order.order_id.order_id,
            previous_status=None,
            lineage_id=order.lineage_id,
            certificate_id=order.certificate_id,
        )
        order.lifecycle.append(event)
        order.status = OrderStatus.RECEIVED

        return order

    # ══════════════════════════════════════════════════
    #  Derived properties
    # ══════════════════════════════════════════════════

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def has_valid_certificate(self) -> bool:
        return bool(self.certificate_id)

    @property
    def notional_value(self) -> float:
        if self.price.has_limit:
            return self.quantity.original * self.price.limit_price
        return 0.0

    @property
    def needs_expiration_check(self) -> bool:
        if not self.expires_at:
            return False
        if self.status.is_terminal:
            return False
        return bool(__import__("time").time() >= self.expires_at)

    # ══════════════════════════════════════════════════
    #  State machine access
    # ══════════════════════════════════════════════════

    def apply_event(self, event: OrderLifecycleEvent) -> Order:
        """Apply a lifecycle event via the state machine."""
        self.lifecycle.append(event)
        self.status = self.lifecycle.current_status
        self.updated_at = __import__("time").time()
        return self

    def apply_fill(self, amount: float, price: float = 0.0) -> None:
        """Apply an execution fill to this order."""
        self.quantity.fill(amount)
        if price > 0:
            self.price.update_fill(price)
        self.updated_at = __import__("time").time()

    # ══════════════════════════════════════════════════
    #  Serialization
    # ══════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id.order_id,
            "client_order_id": self.order_id.client_order_id,
            "parent_order_id": self.order_id.parent_order_id,
            "root_order_id": self.order_id.root_order_id,
            "symbol": self.symbol,
            "side": self.side.name,
            "order_type": self.order_type.name,
            "time_in_force": self.time_in_force.name,
            "original_quantity": self.quantity.original,
            "filled_quantity": self.quantity.filled,
            "remaining_quantity": self.quantity.remaining,
            "cancelled_quantity": self.quantity.cancelled,
            "limit_price": self.price.limit_price,
            "stop_price": self.price.stop_price,
            "average_fill_price": self.price.average_fill_price,
            "status": self.status.name,
            "version": self.version,
            "flow_id": self.flow_id,
            "lineage_id": self.lineage_id,
            "decision_id": self.decision_id,
            "order_intent_id": self.order_intent_id,
            "certificate_id": self.certificate_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "execution_status_unknown": self.execution_status_unknown,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "lifecycle_events": [e.to_dict() for e in self.lifecycle.events],
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        return (
            f"Order({self.order_id.order_id}, {self.side.name} "
            f"{self.quantity.original} {self.symbol} "
            f"[{self.status.name}] lineage={self.lineage_id})"
        )
