"""
Filter Operator — filters events based on a predicate, removing
events that don't match the condition.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)


class FilterOperator:
    """
    Filters elements based on a predicate.

    Keeps only elements for which the predicate returns True.

    Usage::

        op = FilterOperator(lambda e: e["price"] > 0)
        result = await op.apply(trades)  # only positive-price trades
    """

    def __init__(
        self,
        predicate: Callable[[Any], bool],
        *,
        name: str = "filter",
    ) -> None:
        self.predicate = predicate
        self.name = name
        self._apply_count = 0
        self._filtered_count = 0

    async def apply(self, data: Iterable[Any]) -> list[Any]:
        """Apply the filter to a collection."""
        self._apply_count += 1
        result = []
        for item in data:
            if self.predicate(item):
                result.append(item)
            else:
                self._filtered_count += 1
        return result

    @property
    def filtered_count(self) -> int:
        return self._filtered_count

    @property
    def apply_count(self) -> int:
        return self._apply_count
