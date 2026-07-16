"""
Position calculation engine.
"""

from __future__ import annotations

from decimal import Decimal

from .model import Position


class PositionEngine:
    def apply_trade(
        self,
        position: Position,
        quantity: Decimal,
        price: Decimal,
    ) -> Position:
        old_qty = position.quantity
        new_qty = old_qty + quantity

        if old_qty == 0:
            position.average_cost = price

        elif old_qty > 0 and quantity > 0:
            total_cost = (
                old_qty * position.average_cost
                + quantity * price
            )
            position.average_cost = total_cost / new_qty

        elif old_qty > 0 and quantity < 0:
            close_qty = abs(quantity)
            pnl = (price - position.average_cost) * close_qty
            position.realized_pnl += pnl

        position.quantity = new_qty

        return position