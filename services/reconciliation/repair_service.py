"""
Repair service.

Responsible for converting
reconciliation differences into
ledger repair events.
"""

from __future__ import annotations


from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)


from .model import (
    ReconciliationDifference,
)


class RepairService:
    """
    Creates immutable repair events.

    Important:

    Never directly modify position.

    All corrections go through Ledger.
    """

    def create_event(
        self,
        difference: ReconciliationDifference,
    ) -> LedgerEvent:
        """
        Convert difference
        into ledger event.
        """
        if (
            difference.difference_type.value
            ==
            "POSITION_MISMATCH"
        ):
            return LedgerEvent(
                event_type=
                    LedgerEventType.POSITION_ADJUSTED,
                payload={
                    "symbol":
                        difference.symbol,
                    "adjustment":
                        str(
                            difference.delta
                        ),
                    "reason":
                        "RECONCILIATION_REPAIR"
                }
            )

        raise ValueError(
            "Unsupported repair type"
        )