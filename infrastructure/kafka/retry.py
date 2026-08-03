"""
Retry policy.

Defines configurable retry behavior for
failed event processing, supporting
exponential backoff and retry topic routing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetryPolicy:
    """
    Retry policy for event processing.

    Configures how many times a failed event
    should be retried, with what backoff strategy,
    and where retry messages are sent.

    Attributes:
        max_retries: Maximum retry attempts.
        backoff_seconds: Base backoff duration.
        exponential: Use exponential backoff.
        retry_topic_suffix: Suffix for retry topics.
    """

    max_retries: int = 3

    backoff_seconds: float = 1.0

    exponential: bool = True

    retry_topic_suffix: str = ".retry"

    def compute_backoff(
        self,
        attempt: int,
    ) -> float:
        """
        Compute backoff duration for an attempt.

        Args:
            attempt: Current retry attempt (1-based).

        Returns:
            Backoff duration in seconds.
        """

        if self.exponential:
            return self.backoff_seconds * (
                2 ** (attempt - 1)
            )
        else:
            return self.backoff_seconds

    def is_exhausted(
        self,
        retry_count: int,
    ) -> bool:
        """
        Check if retries are exhausted.

        Args:
            retry_count: Current number of retries.

        Returns:
            True if no more retries remain.
        """

        return retry_count >= self.max_retries
