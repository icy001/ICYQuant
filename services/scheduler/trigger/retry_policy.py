"""Retry Policy — configurable retry strategies for trigger evaluation and dispatch.

The :class:`RetryPolicy` defines how the system retries after a transient
failure in trigger evaluation or dispatch.  Multiple backoff strategies are
supported to avoid trigger storms.

Strategies:
* IMMEDIATE — retry right away
* FIXED_DELAY — wait a fixed interval between retries
* EXPONENTIAL_BACKOFF — double the wait each retry
* EXPONENTIAL_BACKOFF_WITH_JITTER — exponential + random jitter
"""

from __future__ import annotations

import enum
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class BackoffStrategy(str, enum.Enum):
    """Backoff algorithm for retry delays."""

    IMMEDIATE = "immediate"
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    EXPONENTIAL_BACKOFF_WITH_JITTER = "exponential_backoff_with_jitter"


@dataclass
class RetryPolicy:
    """Configurable retry policy for trigger operations.

    Usage::

        policy = RetryPolicy(
            max_retries=3,
            strategy=BackoffStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
            base_delay_ms=100,
            max_delay_ms=30_000,
        )
        delay = policy.get_delay(attempt=2)  # ~400ms with jitter
    """

    max_retries: int = 3
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER
    base_delay_ms: int = 100
    max_delay_ms: int = 30_000
    jitter_factor: float = 0.3  # 30% jitter

    def get_delay(self, attempt: int) -> float:
        """Return the delay (in seconds) for the given retry attempt (0-indexed)."""
        if attempt < 0:
            return 0.0

        if self.strategy == BackoffStrategy.IMMEDIATE:
            return 0.0

        if self.strategy == BackoffStrategy.FIXED_DELAY:
            return self.base_delay_ms / 1000.0

        if self.strategy == BackoffStrategy.EXPONENTIAL_BACKOFF:
            delay_ms = self.base_delay_ms * (2 ** attempt)
            return min(delay_ms, self.max_delay_ms) / 1000.0

        if self.strategy == BackoffStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER:
            delay_ms = self.base_delay_ms * (2 ** attempt)
            delay_ms = min(delay_ms, self.max_delay_ms)
            jitter = delay_ms * self.jitter_factor * random.uniform(-1, 1)
            return (delay_ms + jitter) / 1000.0

        return self.base_delay_ms / 1000.0

    def should_retry(self, attempt: int) -> bool:
        """Return True if the given attempt should be retried."""
        return attempt < self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "strategy": self.strategy.value,
            "base_delay_ms": self.base_delay_ms,
            "max_delay_ms": self.max_delay_ms,
            "jitter_factor": self.jitter_factor,
        }

    @classmethod
    def no_retry(cls) -> "RetryPolicy":
        """Convenience: a policy that never retries."""
        return cls(max_retries=0, strategy=BackoffStrategy.IMMEDIATE)

    @classmethod
    def default(cls) -> "RetryPolicy":
        """Convenience: sensible default for most triggers."""
        return cls(
            max_retries=3,
            strategy=BackoffStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
            base_delay_ms=500,
            max_delay_ms=30_000,
        )

    @classmethod
    def aggressive(cls) -> "RetryPolicy":
        """Convenience: aggressive retry for critical triggers."""
        return cls(
            max_retries=10,
            strategy=BackoffStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
            base_delay_ms=100,
            max_delay_ms=10_000,
        )
