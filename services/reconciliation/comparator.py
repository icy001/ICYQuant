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
