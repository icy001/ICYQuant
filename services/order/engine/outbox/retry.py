"""Retry policy for outbox delivery (Commit 33 Part 1.5 #6)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with a hard attempt cap.

    ``delay`` = ``base_delay_seconds * 2 ** retry_count``, capped at
    ``max_delay_seconds``; ``can_retry`` stops once ``max_attempts`` is reached
    - delivery is never retried forever.
    """

    max_attempts: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0

    def delay(self, retry_count: int) -> float:
        value = self.base_delay_seconds * (2 ** retry_count)
        return min(value, self.max_delay_seconds)

    def can_retry(self, retry_count: int) -> bool:
        return retry_count < self.max_attempts
