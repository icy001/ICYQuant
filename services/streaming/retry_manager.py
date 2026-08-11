"""
Retry Manager — configurable retry policies with exponential backoff,
jitter, and circuit breaker integration for stream processing.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryPolicy:
    """Policy configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    jitter_factor: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


class RetryManager:
    """
    Configurable retry manager with exponential backoff and jitter.

    Handles transient failures in stream processing with configurable
    policies, backoff strategies, and DLQ integration.

    Usage::

        mgr = RetryManager(RetryPolicy(max_attempts=3, base_delay_ms=1000))
        result = await mgr.execute(process_event, event)
    """

    def __init__(
        self,
        default_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self.default_policy = default_policy or RetryPolicy()
        self._attempts: dict[str, int] = {}
        self._total_retries = 0
        self._total_successes = 0
        self._total_failures = 0

    def _compute_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Compute the delay for the next retry attempt."""
        if policy.strategy == RetryStrategy.FIXED:
            delay = policy.base_delay_ms
        elif policy.strategy == RetryStrategy.LINEAR:
            delay = policy.base_delay_ms * attempt
        elif policy.strategy == RetryStrategy.EXPONENTIAL:
            delay = policy.base_delay_ms * (2 ** (attempt - 1))
        elif policy.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base = policy.base_delay_ms * (2 ** (attempt - 1))
            jitter = base * policy.jitter_factor * random.random()
            delay = base + jitter
        else:
            delay = policy.base_delay_ms

        return min(delay, policy.max_delay_ms)

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        policy: Optional[RetryPolicy] = None,
        operation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with retry logic."""
        policy = policy or self.default_policy
        last_exception = None

        for attempt in range(1, policy.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._total_successes += 1
                return result

            except policy.retryable_exceptions as e:
                last_exception = e
                self._total_retries += 1

                if attempt < policy.max_attempts:
                    delay = self._compute_delay(attempt, policy)
                    logger.warning(
                        "Retry %d/%d for %s: %s (delay=%dms)",
                        attempt, policy.max_attempts,
                        operation_id or func.__name__, e, int(delay),
                    )
                    await asyncio.sleep(delay / 1000)
                else:
                    logger.error(
                        "All %d retries exhausted for %s: %s",
                        policy.max_attempts, operation_id or func.__name__, e,
                    )

        self._total_failures += 1
        raise last_exception  # type: ignore[misc]

    async def execute_with_dlq(
        self,
        func: Callable[..., Any],
        *args: Any,
        dlq: Any = None,
        topic: str = "",
        policy: Optional[RetryPolicy] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute with retry, sending to DLQ on final failure."""
        try:
            return await self.execute(func, *args, policy=policy, **kwargs)
        except Exception as e:
            if dlq:
                await dlq.send(
                    topic=topic,
                    event=args[0] if args else kwargs,
                    error=str(e),
                )
            raise

    async def stats(self) -> dict[str, Any]:
        """Get retry manager statistics."""
        total = self._total_successes + self._total_failures
        return {
            "total_retries": self._total_retries,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "success_rate": self._total_successes / max(total, 1),
        }
