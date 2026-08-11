"""
Base Position Error hierarchy.
"""

from __future__ import annotations


class PositionError(Exception):
    """Base exception for all Position domain errors."""

    def __init__(self, message: str, code: str = "POSITION_ERROR"):
        super().__init__(message)
        self.code = code


class PositionNotFoundError(PositionError, LookupError):
    """Position not found."""

    def __init__(self, message: str = "Position not found"):
        super().__init__(message, code="POSITION_NOT_FOUND")


class InvalidExecutionError(PositionError):
    """Invalid execution data (zero quantity, negative price, etc.)."""

    def __init__(self, message: str = "Invalid execution data"):
        super().__init__(message, code="INVALID_EXECUTION")


class OverFillError(PositionError):
    """Execution fill exceeds ordered quantity."""

    def __init__(self, message: str = "Execution fill exceeds ordered quantity"):
        super().__init__(message, code="OVER_FILL")


class SequenceGapError(PositionError):
    """Event sequence gap detected — missing intermediate events."""

    def __init__(self, message: str = "Event sequence gap detected"):
        super().__init__(message, code="SEQUENCE_GAP")


class StaleEventError(PositionError):
    """Event version is older than current position version (stale)."""

    def __init__(self, message: str = "Stale event — version is behind current state"):
        super().__init__(message, code="STALE_EVENT")
