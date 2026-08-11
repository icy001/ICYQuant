"""
Position conflict error.

Raised on optimistic concurrency / version mismatch.
"""

from __future__ import annotations

from .position_error import PositionError


class PositionConflictError(PositionError, RuntimeError):
    """Optimistic concurrency / version conflict."""

    def __init__(
        self,
        message: str = "Position version conflict — expected version does not match current",
        expected_version: int = 0,
        actual_version: int = 0,
    ):
        full_msg = f"{message}: expected={expected_version}, actual={actual_version}"
        super().__init__(full_msg, code="VERSION_CONFLICT")
        self.expected_version = expected_version
        self.actual_version = actual_version
