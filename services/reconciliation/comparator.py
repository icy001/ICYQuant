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

from .models.difference import (
    Difference,
    DifferenceType as ModelsDifferenceType,
)
from .models.execution_position import ExecutionPosition
from .models.result import (
    ReconciliationResult as ModelsResult,
)
from .models.snapshot import (
    PositionSnapshot as ModelsSnapshot,
)
from .models.status import (
    ReconciliationStatus as ModelsStatus,
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


class ExecutionPositionComparator:
    """Compare an execution-derived position against the current snapshot."""

    def compare(
        self,
        expected: ExecutionPosition,
        actual: ModelsSnapshot,
    ) -> ModelsResult:
        differences = []

        if expected.quantity != actual.quantity:
            differences.append(
                Difference(
                    type=ModelsDifferenceType.QUANTITY_MISMATCH,
                    expected=expected.quantity,
                    actual=actual.quantity,
                    delta=actual.quantity - expected.quantity,
                )
            )

        if expected.average_price != actual.average_price:
            differences.append(
                Difference(
                    type=ModelsDifferenceType.AVERAGE_PRICE_MISMATCH,
                    expected=expected.average_price,
                    actual=actual.average_price,
                    delta=actual.average_price - expected.average_price,
                )
            )

        if expected.realized_pnl != actual.realized_pnl:
            differences.append(
                Difference(
                    type=ModelsDifferenceType.REALIZED_PNL_MISMATCH,
                    expected=expected.realized_pnl,
                    actual=actual.realized_pnl,
                    delta=actual.realized_pnl - expected.realized_pnl,
                )
            )

        status = (
            ModelsStatus.MATCHED
            if not differences
            else ModelsStatus.MISMATCH
        )

        return ModelsResult(
            symbol=expected.symbol,
            status=status,
            differences=tuple(differences),
        )