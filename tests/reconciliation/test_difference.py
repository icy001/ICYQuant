import pytest
from decimal import Decimal

from services.reconciliation.models.difference import Difference
from services.reconciliation.models.difference import DifferenceType


class TestDifference:
    def test_difference_creation(self):
        diff = Difference(
            type=DifferenceType.QUANTITY_MISMATCH,
            expected=Decimal("100"),
            actual=Decimal("99"),
            delta=Decimal("-1"),
        )
        assert diff.type == DifferenceType.QUANTITY_MISMATCH
        assert diff.expected == Decimal("100")
        assert diff.actual == Decimal("99")
        assert diff.delta == Decimal("-1")

    def test_difference_is_frozen(self):
        diff = Difference(
            type=DifferenceType.QUANTITY_MISMATCH,
            expected=Decimal("100"),
            actual=Decimal("99"),
            delta=Decimal("-1"),
        )
        with pytest.raises(Exception):
            diff.delta = Decimal("0")

    def test_difference_enum_values(self):
        assert DifferenceType.QUANTITY_MISMATCH.value == "QUANTITY_MISMATCH"
        assert DifferenceType.AVERAGE_PRICE_MISMATCH.value == "AVERAGE_PRICE_MISMATCH"
        assert DifferenceType.REALIZED_PNL_MISMATCH.value == "REALIZED_PNL_MISMATCH"
        assert DifferenceType.MULTIPLE_MISMATCH.value == "MULTIPLE_MISMATCH"
        assert DifferenceType.UNKNOWN_MISMATCH.value == "UNKNOWN_MISMATCH"
