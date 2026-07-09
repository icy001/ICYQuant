from services.reconciliation.comparator import ReconciliationComparator
from services.reconciliation.domain_models import LedgerSnapshot, PositionSnapshot


def test_position_mismatch():
    ledger = LedgerSnapshot(
        symbol="NVDA",
        quantity=100,
    )

    position = PositionSnapshot(
        symbol="NVDA",
        quantity=90,
    )

    result = ReconciliationComparator().compare(
        ledger,
        position,
    )

    assert result.difference == 10
    assert result.status.value == "MISMATCH"


def test_position_match():
    ledger = LedgerSnapshot(
        symbol="AAPL",
        quantity=50,
    )

    position = PositionSnapshot(
        symbol="AAPL",
        quantity=50,
    )

    result = ReconciliationComparator().compare(
        ledger,
        position,
    )

    assert result.difference == 0
    assert result.status.value == "MATCHED"
