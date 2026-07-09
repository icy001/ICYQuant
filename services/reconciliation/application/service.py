from services.reconciliation.domain.engine import ReconciliationEngine
from services.reconciliation.domain_models import LedgerSnapshot, PositionSnapshot


class ReconciliationApplicationService:
    def __init__(self) -> None:
        self.engine = ReconciliationEngine()

    def run_reconciliation(
        self,
        ledger_data: dict,
        position_data: dict,
        events: list = None,
    ):
        ledger_snapshot = LedgerSnapshot(
            symbol=ledger_data.get("symbol"),
            quantity=ledger_data.get("quantity"),
        )

        position_snapshot = PositionSnapshot(
            symbol=position_data.get("symbol"),
            quantity=position_data.get("quantity"),
        )

        return self.engine.execute(
            ledger_snapshot,
            position_snapshot,
            events,
        )

    def repair(
        self,
        reconciliation_result,
    ):
        return {"status": "REPAIRED", "result": reconciliation_result}
