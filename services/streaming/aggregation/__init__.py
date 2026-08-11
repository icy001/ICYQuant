"""Aggregation package — stream aggregation operators."""

from .aggregation_engine import AggregationEngine
from .reduce_operator import ReduceOperator
from .fold_operator import FoldOperator
from .join_operator import JoinOperator, JoinType
from .filter_operator import FilterOperator
from .map_operator import MapOperator

__all__ = [
    "AggregationEngine",
    "ReduceOperator",
    "FoldOperator",
    "JoinOperator",
    "JoinType",
    "FilterOperator",
    "MapOperator",
]
