"""
Projection state models.

Projection represents current state
derived from ledger events.

Never modify ledger.
Only rebuild state.
"""

from __future__ import annotations


from dataclasses import (
    dataclass,
    field,
)


from decimal import Decimal


@dataclass
class PositionState:
    """
    Current holding state.
    """

    symbol: str

    quantity: Decimal = Decimal("0")

    average_price: Decimal = Decimal("0")


@dataclass
class CashState:
    """
    Cash account state.
    """

    currency: str = "USD"

    balance: Decimal = Decimal("0")


@dataclass
class PortfolioState:
    """
    Complete portfolio projection.
    """

    positions: dict[str, PositionState] = field(
        default_factory=dict
    )

    cash: dict[str, CashState] = field(
        default_factory=dict
    )

    def get_position(
        self,
        symbol: str,
    ) -> PositionState:
        if symbol not in self.positions:
            self.positions[symbol] = PositionState(
                symbol=symbol
            )

        return self.positions[symbol]