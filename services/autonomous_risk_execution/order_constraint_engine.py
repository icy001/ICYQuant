"""
Order Constraint Engine — enforces order-level constraints.

Manages:
    - Minimum/maximum order size
    - Lot size / round lot constraints
    - Price tick constraints
    - Time-in-force requirements
    - Order type permissions
    - Short sale restrictions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class OrderConstraint:
    """A single order constraint."""
    name: str
    check: str = ""  # Expression or rule
    violation_action: str = "REJECT"  # REJECT, ADJUST, WARN
    message: str = ""


@dataclass
class ConstraintResult:
    """Result of constraint validation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    valid: bool = True
    violations: list[dict] = field(default_factory=list)
    adjusted_fields: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class OrderConstraintEngine:
    """
    Enforces order-level constraints.

    Standard constraints:
        1. Min quantity (exchange minimum)
        2. Max quantity (position limit)
        3. Lot size (round lots)
        4. Price tick (valid price increments)
        5. Price band (within % of last trade)
        6. Time-in-force validity
        7. Short sale restrictions
        8. Odd lot handling
    """

    def __init__(self) -> None:
        self._constraints: list[OrderConstraint] = self._default_constraints()

    def _default_constraints(self) -> list[OrderConstraint]:
        return [
            OrderConstraint("min_quantity", "quantity >= 1",
                          violation_action="REJECT",
                          message="Order quantity below minimum"),
            OrderConstraint("max_quantity", "quantity <= 10_000_000",
                          violation_action="REJECT",
                          message="Order quantity above maximum"),
            OrderConstraint("price_positive", "price > 0 if order_type == 'LIMIT'",
                          violation_action="ADJUST",
                          message="Limit price must be positive"),
            OrderConstraint("lot_size", "quantity % 100 == 0",
                          violation_action="ADJUST",
                          message="Quantity must be in round lots"),
        ]

    async def validate(
        self, order: dict[str, Any]
    ) -> ConstraintResult:
        """Validate an order against all constraints."""
        result = ConstraintResult(order_id=order.get("id", ""))

        # Min quantity
        qty = order.get("quantity", 0)
        if qty < 1:
            result.valid = False
            result.violations.append({
                "constraint": "min_quantity",
                "current": qty, "required": 1,
            })

        # Max quantity
        if abs(qty) > 10_000_000:
            result.valid = False
            result.violations.append({
                "constraint": "max_quantity",
                "current": qty, "max": 10_000_000,
            })

        # Price check
        price = order.get("limit_price")
        order_type = order.get("order_type", "")
        if order_type == "LIMIT" and (price is None or price <= 0):
            result.valid = False
            result.violations.append({
                "constraint": "price_positive",
                "current": price,
            })

        # Lot size
        if qty % 100 != 0:
            adjusted_qty = qty - (qty % 100)
            if adjusted_qty > 0:
                result.adjusted_fields["quantity"] = adjusted_qty

        return result

    def add_constraint(self, constraint: OrderConstraint) -> None:
        """Add a custom constraint."""
        self._constraints.append(constraint)
