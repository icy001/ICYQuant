import pytest
from decimal import Decimal
from typing import List

from services.reconciliation.compare.base import Comparator
from services.reconciliation.compare.manager import ComparatorManager
from services.reconciliation.models.difference import Difference
from services.reconciliation.models.difference import DifferenceType


class MockComparator(Comparator[str]):
    def __init__(self, name: str, differences: List[Difference] = None):
        self._name = name
        self._differences = differences or []

    @property
    def name(self) -> str:
        return self._name

    def compare(
        self,
        internal: List[str],
        external: List[str],
    ) -> List[Difference]:
        return self._differences


class TestComparatorBase:
    def test_comparator_is_abstract(self):
        with pytest.raises(TypeError):
            Comparator[str]()

    def test_mock_comparator_implements_interface(self):
        comparator = MockComparator("test")
        assert comparator.name == "test"
        assert comparator.compare([], []) == []


class TestComparatorManager:
    def test_manager_initializes_empty(self):
        manager = ComparatorManager()
        assert len(manager.comparators) == 0

    def test_manager_register_comparator(self):
        manager = ComparatorManager()
        comparator = MockComparator("test")
        manager.register(comparator)
        assert len(manager.comparators) == 1
        assert manager.comparators[0].name == "test"

    def test_manager_register_multiple_comparators(self):
        manager = ComparatorManager()
        manager.register(MockComparator("comparator1"))
        manager.register(MockComparator("comparator2"))
        manager.register(MockComparator("comparator3"))
        assert len(manager.comparators) == 3
        names = [c.name for c in manager.comparators]
        assert names == ["comparator1", "comparator2", "comparator3"]

    def test_manager_compare_all_with_no_comparators(self):
        manager = ComparatorManager()
        differences = manager.compare_all({}, {})
        assert len(differences) == 0

    def test_manager_compare_all_with_comparator_returning_differences(self):
        manager = ComparatorManager()
        expected_diff = Difference(
            type=DifferenceType.QUANTITY_MISMATCH,
            expected=Decimal("100"),
            actual=Decimal("99"),
            delta=Decimal("-1"),
        )
        comparator = MockComparator("test", [expected_diff])
        manager.register(comparator)
        differences = manager.compare_all({}, {})
        assert len(differences) == 1
        assert differences[0].type == DifferenceType.QUANTITY_MISMATCH
        assert differences[0].delta == Decimal("-1")

    def test_manager_compare_all_aggregates_multiple_comparators(self):
        manager = ComparatorManager()
        diff1 = Difference(
            type=DifferenceType.QUANTITY_MISMATCH,
            expected=Decimal("100"),
            actual=Decimal("99"),
            delta=Decimal("-1"),
        )
        diff2 = Difference(
            type=DifferenceType.AVERAGE_PRICE_MISMATCH,
            expected=Decimal("1000"),
            actual=Decimal("950"),
            delta=Decimal("-50"),
        )
        manager.register(MockComparator("position", [diff1]))
        manager.register(MockComparator("cash", [diff2]))
        differences = manager.compare_all({}, {})
        assert len(differences) == 2

    def test_manager_clear(self):
        manager = ComparatorManager()
        manager.register(MockComparator("test"))
        assert len(manager.comparators) == 1
        manager.clear()
        assert len(manager.comparators) == 0
