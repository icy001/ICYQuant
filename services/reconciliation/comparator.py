"""
State comparator.

Compare:

Internal Projection

vs

External Broker State
"""

from __future__ import annotations


from decimal import Decimal


from services.projection import (
    PortfolioState,
)


from .model import (
    DifferenceType,
    ReconciliationDifference,
)

from .domain_models import (
    LedgerSnapshot,
    PositionSnapshot,
    ReconciliationResult,
    ReconciliationStatus,
)


class ReconciliationComparator:
    def compare(
        self,
        ledger: LedgerSnapshot,
        position: PositionSnapshot,
    ) -> ReconciliationResult:
        diff = ledger.quantity - position.quantity

        status = (
            ReconciliationStatus.MATCHED
            if diff == 0
            else ReconciliationStatus.MISMATCH
        )

        return ReconciliationResult(
            symbol=ledger.symbol,
            ledger_quantity=ledger.quantity,
            position_quantity=position.quantity,
            difference=diff,
            status=status,
        )


class PositionComparator:
    def compare(
        self,
        internal: PortfolioState,
        external: dict[str, Decimal],
    ) -> list[ReconciliationDifference]:
        differences = []

        symbols = set(
            internal.positions.keys()
        ) | set(
            external.keys()
        )

        for symbol in symbols:
            internal_qty = (
                internal.positions
                .get(symbol)
                .quantity
                if symbol in internal.positions
                else Decimal("0")
            )

            external_qty = external.get(
                symbol,
                Decimal("0")
            )

            if internal_qty != external_qty:
                differences.append(
                    ReconciliationDifference(
                        difference_type=
                            DifferenceType.POSITION_MISMATCH,
                        symbol=symbol,
                        expected=internal_qty,
                        actual=external_qty,
                        delta=
                            external_qty -
                            internal_qty,
                        message=(
                            f"{symbol} "
                            f"position mismatch"
                        )
                    )
                )

        return differences