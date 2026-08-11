"""Base recovery exception."""


class RecoveryError(Exception):
    """Base exception for all recovery-related errors."""

    def __init__(self, message: str = "Recovery error"):
        super().__init__(message)
