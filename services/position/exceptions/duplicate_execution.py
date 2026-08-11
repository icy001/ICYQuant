"""
Duplicate execution error.

Raised when the same execution_id has already been applied to a position.
"""

from __future__ import annotations

from .position_error import PositionError


class DuplicateExecutionError(PositionError):
    """Execution ID already processed for this position."""

    def __init__(
        self,
        execution_id: str,
        event_id: str = "",
        message: str = "",
    ):
        msg = message or f"Duplicate execution: exec_id={execution_id}"
        if event_id:
            msg = f"{msg}, event_id={event_id}"
        super().__init__(msg, code="DUPLICATE_EXECUTION")
        self.execution_id = execution_id
        self.event_id = event_id
