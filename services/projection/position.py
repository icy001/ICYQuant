"""
Position projection.

Build position state from:

ORDER_FILLED

events.
"""

from __future__ import annotations


from decimal import Decimal


from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)


from .base import Projection


from .state import PortfolioState


class PositionProjection(Projection):
    """
    Position state builder.
    """

    def __init__(
        self,
        state: PortfolioState,
    ) -> None:
        self.state = state

    def apply(
        self,
        event: LedgerEvent,
    ) -> None:
        if event.event_type != LedgerEventType.ORDER_FILLED:
            return

        symbol = event.payload["symbol"]

        quantity = Decimal(
            str(
                event.payload["quantity"]
            )
        )

        price = Decimal(
            str(
                event.payload["price"]
            )
        )

        position = (
            self.state
            .get_position(symbol)
        )

        old_qty = position.quantity

        new_qty = old_qty + quantity

        if new_qty != 0:
            position.average_price = (
                (
                    old_qty *
                    position.average_price
                )
                +
                (
                    quantity *
                    price
                )
            ) / new_qty

        position.quantity = new_qty