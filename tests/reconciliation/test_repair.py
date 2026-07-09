from services.reconciliation.domain_models import (
    LedgerSnapshot,
    PositionSnapshot,
)
from services.reconciliation.comparator import ReconciliationComparator
from services.reconciliation.repair_engine import RepairEngine


def test_create_repair_command():
    ledger = LedgerSnapshot(
        symbol="NVDA",
        quantity=100,
    )

    position = PositionSnapshot(
        symbol="NVDA",
        quantity=90,
    )

    reconciliation = ReconciliationComparator().compare(
        ledger,
        position,
    )

    command = RepairEngine().create_command(reconciliation)

    assert command.symbol == "NVDA"
    assert command.adjustment == 10


def test_create_repair_command_with_match():
    ledger = LedgerSnapshot(
        symbol="AAPL",
        quantity=50,
    )

    position = PositionSnapshot(
        symbol="AAPL",
        quantity=50,
    )

    reconciliation = ReconciliationComparator().compare(
        ledger,
        position,
    )

    command = RepairEngine().create_command(reconciliation)

    assert command.symbol == "AAPL"
    assert command.adjustment == 0
