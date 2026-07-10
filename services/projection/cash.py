"""
Cash projection.

Handles:

CASH_DEPOSITED

CASH_WITHDRAWN

COMMISSION_CHARGED
"""

from __future__ import annotations


from decimal import Decimal


from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)


from .base import Projection


from .state import CashState, PortfolioState


class CashProjection(Projection):
    def __init__(
        self,
        state: PortfolioState,
    ) -> None:
        self.state = state

    def apply(
        self,
        event: LedgerEvent,
    ) -> None:
        if event.event_type not in (
            LedgerEventType.CASH_DEPOSITED,
            LedgerEventType.CASH_WITHDRAWN,
            LedgerEventType.COMMISSION_CHARGED,
        ):
            return

        currency = event.payload.get(
            "currency",
            "USD"
        )

        if currency not in self.state.cash:
            self.state.cash[currency] = CashState(
                currency=currency
            )

        cash = self.state.cash[currency]

        amount = Decimal(
            str(
                event.payload["amount"]
            )
        )

        if event.event_type == LedgerEventType.CASH_DEPOSITED:
            cash.balance += amount

        elif event.event_type == LedgerEventType.CASH_WITHDRAWN:
            cash.balance -= amount

        elif event.event_type == LedgerEventType.COMMISSION_CHARGED:
            cash.balance -= amount