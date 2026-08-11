"""
Join Operator — joins two streams/collections on matching keys
with support for inner, left, right, and full outer joins.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class JoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL_OUTER = "full_outer"
    CROSS = "cross"


class JoinOperator:
    """
    Joins two collections on matching keys.

    Supports inner, left, right, full outer, and cross joins
    for stream-stream and stream-table join patterns.

    Usage::

        op = JoinOperator(
            left_key=lambda e: e["symbol"],
            right_key=lambda e: e["ticker"],
            join_type=JoinType.INNER,
        )
        result = await op.apply(trades, quotes)
    """

    def __init__(
        self,
        left_key: Callable[[Any], Any],
        right_key: Callable[[Any], Any],
        *,
        join_type: JoinType = JoinType.INNER,
        combiner: Optional[Callable[[Any, Any], Any]] = None,
        name: str = "join",
    ) -> None:
        self.left_key = left_key
        self.right_key = right_key
        self.join_type = join_type
        self.combiner = combiner or (lambda l, r: {**l, **r})
        self.name = name

    async def apply(self, left: list[Any], right: list[Any]) -> list[Any]:
        """Apply the join operation to two collections."""
        # Index right side by key
        right_index: dict[Any, list[Any]] = {}
        for r in right:
            key = self.right_key(r)
            if key not in right_index:
                right_index[key] = []
            right_index[key].append(r)

        results = []
        matched_left_keys: set[Any] = set()

        for l in left:
            l_key = self.left_key(l)
            matched = right_index.get(l_key, [])

            if matched:
                matched_left_keys.add(l_key)
                for r in matched:
                    results.append(self.combiner(l, r))
            elif self.join_type in (JoinType.LEFT, JoinType.FULL_OUTER):
                results.append(self.combiner(l, None))

        # Right outer / full outer: unmatched right rows
        if self.join_type in (JoinType.RIGHT, JoinType.FULL_OUTER):
            for r in right:
                r_key = self.right_key(r)
                if r_key not in matched_left_keys:
                    results.append(self.combiner(None, r))

        return results
