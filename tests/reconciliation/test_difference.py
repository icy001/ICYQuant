import pytest

from services.reconciliation.models.difference import Difference
from services.reconciliation.models.types import DifferenceType


class TestDifference:
    def test_difference_creation(self):
        diff = Difference(
            diff_type=DifferenceType.POSITION,
            entity_id="AAPL",
            expected=100.0,
            actual=99.0,
            message="Position mismatch",
        )
        assert diff.diff_type == DifferenceType.POSITION
        assert diff.entity_id == "AAPL"
        assert diff.expected == 100.0
        assert diff.actual == 99.0
        assert diff.message == "Position mismatch"

    def test_difference_default_message(self):
        diff = Difference(
            diff_type=DifferenceType.CASH,
            entity_id="user1",
            expected=1000.0,
            actual=950.0,
        )
        assert diff.message == ""

    def test_difference_enum_values(self):
        assert DifferenceType.POSITION.value == "POSITION"
        assert DifferenceType.CASH.value == "CASH"
        assert DifferenceType.ORDER.value == "ORDER"
        assert DifferenceType.TRADE.value == "TRADE"
        assert DifferenceType.ACCOUNT.value == "ACCOUNT"
