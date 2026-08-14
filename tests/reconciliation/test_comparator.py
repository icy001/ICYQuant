from decimal import Decimal

from services.reconciliation.comparator import ExecutionPositionComparator
from services.reconciliation.models.difference import DifferenceType
from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.models.snapshot import PositionSnapshot
from services.reconciliation.models.status import ReconciliationStatus


def make_execution_position(**overrides):
    fields = {
        "symbol": "AAPL",
        "quantity": Decimal("100"),
        "average_price": Decimal("150"),
        "realized_pnl": Decimal("0"),
    }
    fields.update(overrides)
    return ExecutionPosition(**fields)


def make_position_snapshot(**overrides):
    fields = {
        "symbol": "AAPL",
        "quantity": Decimal("100"),
        "average_price": Decimal("150"),
        "realized_pnl": Decimal("0"),
    }
    fields.update(overrides)
    return PositionSnapshot(**fields)


def test_quantity_mismatch_classification():
    expected = make_execution_position(quantity=Decimal("100"))
    actual = make_position_snapshot(quantity=Decimal("80"))

    result = ExecutionPositionComparator().compare(expected, actual)

    assert result.status == ReconciliationStatus.MISMATCH
    assert len(result.differences) == 1

    difference = result.differences[0]
    assert difference.type == DifferenceType.QUANTITY_MISMATCH
    assert difference.expected == Decimal("100")
    assert difference.actual == Decimal("80")
    assert difference.delta == Decimal("-20")


def test_average_price_mismatch_classification():
    expected = make_execution_position(average_price=Decimal("150"))
    actual = make_position_snapshot(average_price=Decimal("160"))

    result = ExecutionPositionComparator().compare(expected, actual)

    assert result.status == ReconciliationStatus.MISMATCH
    assert len(result.differences) == 1

    difference = result.differences[0]
    assert difference.type == DifferenceType.AVERAGE_PRICE_MISMATCH
    assert difference.expected == Decimal("150")
    assert difference.actual == Decimal("160")
    assert difference.delta == Decimal("10")


def test_realized_pnl_mismatch_classification():
    expected = make_execution_position(realized_pnl=Decimal("1200"))
    actual = make_position_snapshot(realized_pnl=Decimal("900"))

    result = ExecutionPositionComparator().compare(expected, actual)

    assert result.status == ReconciliationStatus.MISMATCH
    assert len(result.differences) == 1

    difference = result.differences[0]
    assert difference.type == DifferenceType.REALIZED_PNL_MISMATCH
    assert difference.expected == Decimal("1200")
    assert difference.actual == Decimal("900")
    assert difference.delta == Decimal("-300")


def test_multiple_mismatch_classification():
    expected = make_execution_position(
        quantity=Decimal("100"),
        realized_pnl=Decimal("1200"),
    )
    actual = make_position_snapshot(
        quantity=Decimal("80"),
        realized_pnl=Decimal("900"),
    )

    result = ExecutionPositionComparator().compare(expected, actual)

    assert result.status == ReconciliationStatus.MISMATCH
    assert len(result.differences) == 2

    types = {difference.type for difference in result.differences}
    assert types == {
        DifferenceType.QUANTITY_MISMATCH,
        DifferenceType.REALIZED_PNL_MISMATCH,
    }


def test_matched_has_no_differences():
    expected = make_execution_position()
    actual = make_position_snapshot()

    result = ExecutionPositionComparator().compare(expected, actual)

    assert result.status == ReconciliationStatus.MATCHED
    assert result.differences == ()
