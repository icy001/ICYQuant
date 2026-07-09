from typing import Any, Dict, List

from services.reconciliation.compare.base import Comparator
from services.reconciliation.models.difference import Difference


class ComparatorManager:
    def __init__(self) -> None:
        self._comparators: List[Comparator] = []

    def register(self, comparator: Comparator) -> None:
        self._comparators.append(comparator)

    def compare_all(
        self,
        internal_data: Dict[str, Any],
        external_data: Dict[str, Any],
    ) -> List[Difference]:
        differences: List[Difference] = []

        for comparator in self._comparators:
            result = comparator.compare(
                internal_data,
                external_data,
            )
            differences.extend(result)

        return differences

    @property
    def comparators(self) -> List[Comparator]:
        return list(self._comparators)

    def clear(self) -> None:
        self._comparators = []
