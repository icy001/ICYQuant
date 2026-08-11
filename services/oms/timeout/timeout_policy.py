"""TimeoutPolicy — timeout configuration for execution operations."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimeoutPolicy:
    """Timeout settings for execution operations.

    All timeouts are in seconds. When a timeout expires, the order
    enters UNKNOWN state (not FAILED) and recovery is triggered.
    """

    submission_timeout: float = 5.0
    ack_timeout: float = 10.0
    cancel_timeout: float = 5.0
    execution_report_timeout: float = 30.0
    query_timeout: float = 3.0

    @classmethod
    def default(cls) -> "TimeoutPolicy":
        return cls()

    @classmethod
    def fast_market(cls) -> "TimeoutPolicy":
        """Shorter timeouts for fast markets."""
        return cls(
            submission_timeout=2.0,
            ack_timeout=5.0,
            cancel_timeout=2.0,
            execution_report_timeout=10.0,
            query_timeout=2.0,
        )

    @classmethod
    def relaxed(cls) -> "TimeoutPolicy":
        """Longer timeouts for slow/illiquid markets."""
        return cls(
            submission_timeout=10.0,
            ack_timeout=30.0,
            cancel_timeout=10.0,
            execution_report_timeout=120.0,
            query_timeout=5.0,
        )
