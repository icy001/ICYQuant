from __future__ import annotations

from decimal import Decimal

from .models.execution_position import ExecutionPosition


class ExecutionPositionBuilder:
    """Rebuild a position from a stream of execution events."""

    def build(self, events) -> ExecutionPosition:
        symbol = ""
        quantity = Decimal("0")
        average_price = Decimal("0")
        realized_pnl = Decimal("0")

        for event in events:
            if not symbol:
                symbol = event.symbol

            qty = Decimal(str(event.quantity))
            price = Decimal(str(event.price))

            signed = qty if event.side == "BUY" else -qty

            quantity, average_price, realized_pnl = self._apply(
                quantity=quantity,
                average_price=average_price,
                realized_pnl=realized_pnl,
                signed=signed,
                price=price,
            )

        return ExecutionPosition(
            symbol=symbol,
            quantity=quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
        )

    @staticmethod
    def _apply(
        quantity: Decimal,
        average_price: Decimal,
        realized_pnl: Decimal,
        signed: Decimal,
        price: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        old_qty = quantity
        new_qty = old_qty + signed

        if old_qty == 0:
            average_price = price
        elif old_qty > 0 and signed > 0:
            total_cost = old_qty * average_price + signed * price
            average_price = total_cost / new_qty
        elif old_qty > 0 and signed < 0:
            close_qty = min(-signed, old_qty)
            realized_pnl += (price - average_price) * close_qty
            if new_qty < 0:
                average_price = price
        elif old_qty < 0 and signed < 0:
            total_cost = abs(old_qty) * average_price + abs(signed) * price
            average_price = total_cost / abs(new_qty)
        elif old_qty < 0 and signed > 0:
            close_qty = min(signed, abs(old_qty))
            realized_pnl += (average_price - price) * close_qty
            if new_qty > 0:
                average_price = price

        return new_qty, average_price, realized_pnl
