"""
Reduce Operator — combines elements of a collection into a single
result using an associative binary operation.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
U = TypeVar("U")


class ReduceOperator:
    """
    Reduces elements into a single result using a binary operation.

    Similar to Python's functools.reduce, operates on collections
    with an optional initial value.

    Usage::

        op = ReduceOperator(lambda a, b: a + b, initial=0)
        result = await op.apply([1, 2, 3, 4])  # → 10

        op2 = ReduceOperator(lambda a, b: a * b, initial=1)
        result = await op2.apply([1, 2, 3, 4])  # → 24
    """

    def __init__(
        self,
        func: Callable[[Any, Any], Any],
        initial: Any = None,
        *,
        name: str = "reduce",
    ) -> None:
        self.func = func
        self.initial = initial
        self.name = name
        self._apply_count = 0

    async def apply(self, data: Iterable[Any]) -> Any:
        """Apply the reduce operation to a collection."""
        self._apply_count += 1
        iterator = iter(data)

        try:
            if self.initial is not None:
                result = self.initial
            else:
                result = next(iterator)

            for item in iterator:
                result = self.func(result, item)

            return result
        except StopIteration:
            return self.initial
