"""Retry policy for span export."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional


class RetryPolicy:
    """
    Retry policy for export operations.

    Implements exponential backoff retry
    with configurable max retries and
    jitter support.

    Strategy:
    1s -> 2s -> 4s -> 8s -> 16s

    Usage:
        policy = RetryPolicy(max_retry=5)
        result = await policy.execute(export_fn, spans)
    """

    def __init__(
        self,
        max_retry: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
        jitter: bool = True,
    ) -> None:
        self._max_retry = max_retry
        self._initial_delay = initial_delay
        self._max_delay = max_delay
        self._exponential = exponential_backoff
        self._jitter = jitter
        self._retry_count: int = 0
        self._total_delay: float = 0.0

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def get_delay(self, attempt: int) -> float:
        """Get delay for a specific attempt."""
        if self._exponential:
            delay = self._initial_delay * (2 ** attempt)
        else:
            delay = self._initial_delay
        delay = min(delay, self._max_delay)
        if self._jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)
        return delay

    async def execute(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Execute a function with retry.

        Args:
            fn: Async function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            True if succeeded, False if all retries failed.
        """

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retry + 1):
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retry:
                    delay = self.get_delay(attempt)
                    self._total_delay += delay
                    self._retry_count += 1
                    await asyncio.sleep(delay)
        return False

    def get_stats(self) -> dict:
        return {
            "max_retry": self._max_retry,
            "retry_count": self._retry_count,
            "total_delay": round(self._total_delay, 2),
        }
