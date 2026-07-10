"""
Reconciliation engine.
"""

from __future__ import annotations

from decimal import Decimal

from services.projection import (
    PortfolioState,
    PositionState,
)


from .comparator import (
    PositionComparator,
)


class ReconciliationEngine:
    def __init__(self):
        self.position_comparator = (
            PositionComparator()
        )

    def reconcile_positions(
        self,
        internal,
        external,
    ):
        if isinstance(internal, dict):
            portfolio_state = PortfolioState()
            for symbol, quantity in internal.items():
                portfolio_state.positions[symbol] = PositionState(
                    symbol=symbol,
                    quantity=Decimal(str(quantity)),
                )
        else:
            portfolio_state = internal

        if isinstance(external, dict) and not (
            isinstance(list(external.values())[0], Decimal)
            if external
            else False
        ):
            external_decimal = {
                symbol: Decimal(str(quantity))
                for symbol, quantity in external.items()
            }
        else:
            external_decimal = external

        return (
            self.position_comparator
            .compare(
                portfolio_state,
                external_decimal
            )
        )