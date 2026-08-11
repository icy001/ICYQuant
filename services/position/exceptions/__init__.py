"""
Position domain exceptions.

position_error      — base error class for all position exceptions.
duplicate_execution — same execution_id already processed.
position_conflict   — optimistic concurrency / version conflict.
"""

from __future__ import annotations

from .duplicate_execution import DuplicateExecutionError
from .position_conflict import PositionConflictError
from .position_error import (
    InvalidExecutionError,
    OverFillError,
    PositionError,
    PositionNotFoundError,
    SequenceGapError,
    StaleEventError,
)

__all__ = [
    "PositionError",
    "PositionNotFoundError",
    "PositionConflictError",
    "DuplicateExecutionError",
    "InvalidExecutionError",
    "OverFillError",
    "SequenceGapError",
    "StaleEventError",
]
