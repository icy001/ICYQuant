"""
Aggregation Engine — unified stream aggregation engine coordinating
reduce, fold, join, filter, and map operators for windowed computation.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

from .reduce_operator import ReduceOperator
from .fold_operator import FoldOperator
from .join_operator import JoinOperator, JoinType
from .filter_operator import FilterOperator
from .map_operator import MapOperator


class AggregationEngine:
    """
    Unified stream aggregation engine.

    Coordinates reduce, fold, join, filter, and map operators
    across windowed and non-windowed stream data.

    Pipeline: Map → Filter → Reduce → Fold → Join

    Usage::

        engine = AggregationEngine()
        result = await engine.aggregate(events, pipeline=[
            MapOperator(lambda e: e["price"] * e["volume"]),
            FilterOperator(lambda e: e > 0),
            ReduceOperator(sum, initial=0),
        ])
    """

    def __init__(self) -> None:
        self._operators: dict[str, Any] = {}
        self._pipeline_count = 0

    async def aggregate(
        self,
        data: Any,
        pipeline: list[Any],
        *,
        window_context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Execute an aggregation pipeline on data."""
        current = data
        for operator in pipeline:
            if isinstance(operator, MapOperator):
                current = await operator.apply(current)
            elif isinstance(operator, FilterOperator):
                current = await operator.apply(current)
            elif isinstance(operator, ReduceOperator):
                current = await operator.apply(current)
            elif isinstance(operator, FoldOperator):
                current = await operator.apply(current)
            elif isinstance(operator, JoinOperator):
                if window_context:
                    current = await operator.apply(current, window_context.get("right", []))
                else:
                    current = current
            else:
                logger.warning("Unknown operator in pipeline: %s", type(operator))

        self._pipeline_count += 1
        return current

    async def aggregate_windowed(
        self,
        window_results: list[Any],
        pipeline: list[Any],
    ) -> list[Any]:
        """Apply aggregation pipeline to each window result."""
        return [
            await self.aggregate(wr, pipeline)
            for wr in window_results
        ]

    @property
    def pipeline_count(self) -> int:
        return self._pipeline_count
