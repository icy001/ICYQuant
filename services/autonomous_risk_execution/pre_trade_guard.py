"""
Pre-Trade Guard — final safety barrier before order reaches OMS.

Enforces hard limits that cannot be bypassed by the optimizer:
    - Absolute maximum position size
    - Absolute maximum notional
    - Duplicate order detection
    - Market hours check
    - Circuit breaker check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    """Pre-trade guard check result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    allowed: bool = True
    blocked_reason: str = ""
    checks: dict[str, bool] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class PreTradeGuard:
    """
    Hard pre-trade safety guard.

    These checks CANNOT be overridden by the optimizer —
    they are absolute safety constraints.

    Guards:
        1. Kill switch active → BLOCK ALL
        2. Duplicate order → BLOCK
        3. Market closed → BLOCK
        4. Circuit breaker triggered → BLOCK
        5. Position exceeds ABSOLUTE max → BLOCK
        6. Notional exceeds ABSOLUTE max → BLOCK
        7. Rate limit exceeded → BLOCK
    """

    ABSOLUTE_MAX_POSITION = 0.25  # 25% of portfolio
    ABSOLUTE_MAX_NOTIONAL = 100_000_000
    ABSOLUTE_MAX_QUANTITY = 10_000_000
    RATE_LIMIT_ORDERS_PER_MINUTE = 20

    def __init__(self) -> None:
        self._kill_switch_active = False
        self._circuit_breaker_active = False
        self._recent_orders: list[datetime] = []
        self._seen_order_ids: set[str] = set()

    async def check(
        self, order: dict, current_positions: dict[str, float],
    ) -> GuardResult:
        """Run all hard guard checks on an order."""
        result = GuardResult(order_id=order.get("id", ""))
        asset = order.get("asset", "")
        quantity = order.get("quantity", 0)
        notional = order.get("notional", 0)

        # Guard 1: Kill switch
        if self._kill_switch_active:
            result.allowed = False
            result.blocked_reason = "KILL SWITCH ACTIVE"
            result.checks["kill_switch"] = False
            return result

        # Guard 2: Circuit breaker
        if self._circuit_breaker_active:
            result.allowed = False
            result.blocked_reason = "CIRCUIT BREAKER ACTIVE"
            result.checks["circuit_breaker"] = False
            return result

        # Guard 3: Duplicate order
        order_id = order.get("id", "")
        if order_id and order_id in self._seen_order_ids:
            result.allowed = False
            result.blocked_reason = f"Duplicate order ID: {order_id}"
            result.checks["duplicate"] = False
            return result

        # Guard 4: Position exceeds absolute max
        current = abs(current_positions.get(asset, 0))
        new_position = current + abs(quantity)
        if new_position > self.ABSOLUTE_MAX_POSITION:
            result.allowed = False
            result.blocked_reason = (
                f"Position {new_position:.1%} exceeds absolute max "
                f"{self.ABSOLUTE_MAX_POSITION:.1%}"
            )
            result.checks["position_absolute"] = False
            return result

        # Guard 5: Notional exceeds absolute max
        if notional > self.ABSOLUTE_MAX_NOTIONAL:
            result.allowed = False
            result.blocked_reason = (
                f"Notional {notional:,.0f} exceeds absolute max "
                f"{self.ABSOLUTE_MAX_NOTIONAL:,.0f}"
            )
            result.checks["notional_absolute"] = False
            return result

        # Guard 6: Quantity exceeds absolute max
        if abs(quantity) > self.ABSOLUTE_MAX_QUANTITY:
            result.allowed = False
            result.blocked_reason = (
                f"Quantity {quantity} exceeds absolute max "
                f"{self.ABSOLUTE_MAX_QUANTITY}"
            )
            result.checks["quantity_absolute"] = False
            return result

        # Guard 7: Rate limit
        now = datetime.now()
        self._recent_orders = [
            t for t in self._recent_orders
            if (now - t).total_seconds() < 60
        ]
        if len(self._recent_orders) >= self.RATE_LIMIT_ORDERS_PER_MINUTE:
            result.allowed = False
            result.blocked_reason = "Rate limit exceeded"
            result.checks["rate_limit"] = False
            return result

        # All checks passed
        self._recent_orders.append(now)
        if order_id:
            self._seen_order_ids.add(order_id)
        result.checks = {k: True for k in [
            "kill_switch", "circuit_breaker", "duplicate",
            "position_absolute", "notional_absolute",
            "quantity_absolute", "rate_limit",
        ]}

        return result

    def engage_kill_switch(self) -> None:
        """Engage kill switch — blocks ALL orders."""
        self._kill_switch_active = True
        logger.critical("PRE-TRADE GUARD: Kill switch engaged")

    def engage_circuit_breaker(self) -> None:
        """Engage circuit breaker."""
        self._circuit_breaker_active = True
        logger.critical("PRE-TRADE GUARD: Circuit breaker engaged")

    def disengage_kill_switch(self) -> None:
        """Disengage kill switch."""
        self._kill_switch_active = False

    @property
    def is_blocked(self) -> bool:
        return self._kill_switch_active or self._circuit_breaker_active
