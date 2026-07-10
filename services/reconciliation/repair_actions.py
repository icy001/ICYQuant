"""
Repair actions.

Reconciliation does not directly
modify state.

It creates repair events.
"""

from __future__ import annotations


from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)


class RepairBuilder:
    def create_position_adjustment(
        self,
        symbol: str,
        quantity,
    ) -> LedgerEvent:
        return LedgerEvent(
            event_type=
                LedgerEventType.POSITION_ADJUSTED,
            payload={
                "symbol":
                    symbol,
                "quantity":
                    quantity,
            }
        )