"""
Map Operator — transforms each element in a collection using a
mapping function, producing a new collection.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)


class MapOperator:
    """
    Transforms each element using a mapping function.

    One-to-one transformation of stream elements.

    Usage::

        op = MapOperator(lambda e: {"symbol": e["s"], "px": e["price"] * e["qty"]})
        result = await op.apply(trades)
    """

    def __init__(
        self,
        func: Callable[[Any], Any],
        *,
        name: str = "map",
    ) -> None:
        self.func = func
        self.name = name
        self._apply_count = 0

    async def apply(self, data: Iterable[Any]) -> list[Any]:
        """Apply the map function to each element."""
        self._apply_count += 1
        return [self.func(item) for item in data]

    @property
    def apply_count(self) -> int:
        return self._apply_count
