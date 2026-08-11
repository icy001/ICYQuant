"""
Fold Operator — accumulates values using an initial accumulator and
a combining function, producing intermediate results at each step.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)


class FoldOperator:
    """
    Folds elements with an initial accumulator, producing intermediate
    results at each step. Unlike reduce which produces a single result,
    fold can emit the accumulator state after each element.

    Usage::

        op = FoldOperator(
            func=lambda acc, e: acc + e["volume"],
            initial=0,
        )
        states = await op.apply(trades)  # → [100, 250, 400, ...]
    """

    def __init__(
        self,
        func: Callable[[Any, Any], Any],
        initial: Any,
        *,
        name: str = "fold",
        emit_intermediate: bool = False,
    ) -> None:
        self.func = func
        self.initial = initial
        self.name = name
        self.emit_intermediate = emit_intermediate
        self._accumulator: Any = None
        self._apply_count = 0

    async def apply(self, data: Iterable[Any]) -> Any:
        """Apply the fold operation to a collection."""
        self._apply_count += 1
        self._accumulator = self.initial

        intermediates = []
        for item in data:
            self._accumulator = self.func(self._accumulator, item)
            if self.emit_intermediate:
                intermediates.append(self._accumulator)

        if self.emit_intermediate:
            return intermediates
        return self._accumulator

    async def reset(self) -> None:
        """Reset the accumulator."""
        self._accumulator = self.initial

    @property
    def current_value(self) -> Any:
        return self._accumulator
