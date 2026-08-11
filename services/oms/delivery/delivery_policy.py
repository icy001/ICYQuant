"""DeliveryPolicy — retry and timeout configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass
class DeliveryPolicy:
    """Policy for request delivery and retries.

    Fields:
        max_attempts: Maximum number of delivery attempts.
        initial_backoff_ms: Initial backoff in milliseconds.
        max_backoff_ms: Maximum backoff cap.
        backoff_multiplier: Multiplier for exponential backoff.
        timeout_ms: Per-attempt timeout in milliseconds.
        retryable_errors: Error codes that allow retry.
        non_retryable_errors: Error codes that never retry.
    """

    max_attempts: int = 3
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 5000
    backoff_multiplier: float = 2.0
    timeout_ms: int = 5000
    retryable_errors: FrozenSet[str] = frozenset({
        "NETWORK_TIMEOUT",
        "NETWORK_ERROR",
        "CONNECTION_RESET",
        "SERVICE_UNAVAILABLE",
        "RATE_LIMITED",
    })
    non_retryable_errors: FrozenSet[str] = frozenset({
        "INVALID_REQUEST",
        "AUTHENTICATION_FAILED",
        "AUTHORIZATION_FAILED",
        "VENUE_REJECTED",
        "INVALID_ORDER",
    })

    @classmethod
    def default(cls) -> "DeliveryPolicy":
        return cls()

    @classmethod
    def aggressive(cls) -> "DeliveryPolicy":
        """More retries, shorter backoff — for critical orders."""
        return cls(max_attempts=5, initial_backoff_ms=50,
                    max_backoff_ms=2000, timeout_ms=3000)

    @classmethod
    def conservative(cls) -> "DeliveryPolicy":
        """Fewer retries, longer backoff — for non-critical."""
        return cls(max_attempts=2, initial_backoff_ms=500,
                    max_backoff_ms=10000, timeout_ms=10000)

    def is_retryable(self, error_code: str) -> bool:
        """Check if an error code is retryable."""
        if error_code in self.non_retryable_errors:
            return False
        return error_code in self.retryable_errors

    def get_backoff_ms(self, attempt: int) -> int:
        """Calculate backoff for a given attempt number."""
        backoff = self.initial_backoff_ms * (self.backoff_multiplier ** (attempt - 1))
        return min(int(backoff), self.max_backoff_ms)
