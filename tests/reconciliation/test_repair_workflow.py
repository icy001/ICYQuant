from services.reconciliation.domain_models import (
    LedgerSnapshot,
    PositionSnapshot,
)
from services.reconciliation.comparator import ReconciliationComparator
from services.reconciliation.repair_engine import RepairWorkflow


def test_repair_workflow():
    ledger = LedgerSnapshot(symbol="NVDA", quantity=130)
    position = PositionSnapshot(symbol="NVDA", quantity=100)

    reconciliation = ReconciliationComparator().compare(ledger, position)

    workflow = RepairWorkflow()
    result = workflow.repair(reconciliation, rebuilt_position=130)

    assert result["symbol"] == "NVDA"
    assert result["old"] == 100
    assert result["new"] == 130
    assert result["status"] == "REPAIRED"


def test_repair_workflow_with_audit():
    ledger = LedgerSnapshot(symbol="AAPL", quantity=50)
    position = PositionSnapshot(symbol="AAPL", quantity=40)

    reconciliation = ReconciliationComparator().compare(ledger, position)

    workflow = RepairWorkflow()
    workflow.repair(reconciliation, rebuilt_position=50)

    assert len(workflow.audit.get_records()) == 1
    record = workflow.audit.get_records()[0]
    assert record.action == "REPAIR"
    assert record.symbol == "AAPL"
    assert record.before == 40
    assert record.after == 50
