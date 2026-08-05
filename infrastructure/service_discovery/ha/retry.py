"""Adaptive retry engine with budget control for ICYQuant HA.

Provides ``AdaptiveRetryEngine`` with exponential backoff,
decorrelated jitter, and ``RetryBudget`` for rate-limited
retry attempts.

Based on: Exponential backoff with decorrelated jitter
          and adaptive budget consumption.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class RetryBudget:
    """Token-bucket-based retry budget.

    Controls the maximum number of retry attempts within a
    configurable time window. Tokens refill over time.

    Args:
        max_retries: Maximum retries allowed within the window.
        window: Time window in seconds for the budget.
    """

    def __init__(
        self,
        max_retries: int = 5,
        window: float = 60.0,
    ) -> None:
        self._max_retries = max(int(max_retries), 1)
        self._window = float(window) if window > 0 else 60.0
        self._lock = threading.RLock()
        self._tokens = float(self._max_retries)
        self._last_refill = time.time()
        self._consumed = 0
        self._rejected = 0

    # ── Public API ──

    def consume(self) -> bool:
        """Try to consume a retry token.

        Returns:
            True if a token was successfully consumed, False if
            the budget is exhausted.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self._consumed += 1
                return True
            self._rejected += 1
            return False

    def remaining(self) -> int:
        """Return the number of remaining retry tokens."""
        with self._lock:
            self._refill()
            return int(self._tokens)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the budget."""
        with self._lock:
            self._refill()
            return {
                "max_retries": self._max_retries,
                "window": self._window,
                "tokens_remaining": int(self._tokens),
                "consumed": self._consumed,
                "rejected": self._rejected,
                "utilization": (
                    self._consumed
                    / max(self._consumed + int(self._tokens), 1)
                ),
            }

    # ── Internal ──

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill
        if elapsed > 0:
            rate = self._max_retries / self._window
            self._tokens = min(
                self._max_retries,
                self._tokens + elapsed * rate,
            )
            self._last_refill = now

    def __repr__(self) -> str:
        with self._lock:
            self._refill()
            return (
                f"RetryBudget(tokens={int(self._tokens)}/{self._max_retries}, "
                f"window={self._window}s)"
            )


class AdaptiveRetryEngine:
    """Adaptive retry engine with exponential backoff.

    Supports decorrelated jitter and budget-controlled execution.

    Args:
        max_retries: Maximum retry attempts per operation.
        base_delay: Base delay in seconds for backoff.
        max_delay: Maximum delay cap in seconds.
        jitter: Jitter factor (0.0 to 1.0) for randomness.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 30.0,
        jitter: float = 0.1,
    ) -> None:
        self._max_retries = max(int(max_retries), 0)
        self._base_delay = float(base_delay) if base_delay > 0 else 0.1
        self._max_delay = float(max_delay) if max_delay > 0 else 30.0
        self._jitter = min(max(float(jitter), 0.0), 1.0)
        self._lock = threading.RLock()
        self._retry_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_latency = 0.0

    # ── Public API ──

    async def execute(
        self, operation: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        """Execute an operation with automatic retries.

        Args:
            operation: The callable to execute.
            *args: Positional arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            The return value of the operation.

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exception: Optional[BaseException] = None
        last_delay = 0.0
        start = time.monotonic()

        for attempt in range(self._max_retries + 1):
            try:
                result = operation(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                with self._lock:
                    self._success_count += 1
                    self._total_latency += time.monotonic() - start
                return result
            except Exception as exc:
                last_exception = exc
                if attempt >= self._max_retries:
                    break
                last_delay = self._compute_delay(attempt, last_delay)
                with self._lock:
                    self._retry_count += 1
                logger.debug(
                    "Retry %d/%d after %.3fs: %s",
                    attempt + 1,
                    self._max_retries,
                    last_delay,
                    exc,
                )
                await asyncio.sleep(last_delay)

        with self._lock:
            self._failure_count += 1
            self._total_latency += time.monotonic() - start
        raise last_exception  # type: ignore[misc]

    async def execute_with_budget(
        self,
        operation: Callable,
        budget: RetryBudget,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute with retries, consuming budget tokens per retry.

        Args:
            operation: The callable to execute.
            budget: The ``RetryBudget`` to consume tokens from.
            *args: Positional arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            The return value of the operation.

        Raises:
            The last exception if budget or retries are exhausted.
        """
        last_exception: Optional[BaseException] = None
        last_delay = 0.0
        start = time.monotonic()

        for attempt in range(self._max_retries + 1):
            try:
                result = operation(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                with self._lock:
                    self._success_count += 1
                    self._total_latency += time.monotonic() - start
                return result
            except Exception as exc:
                last_exception = exc
                if attempt >= self._max_retries:
                    break
                if not budget.consume():
                    logger.warning(
                        "Retry budget exhausted after %d attempts.",
                        attempt,
                    )
                    break
                last_delay = self._compute_delay(attempt, last_delay)
                with self._lock:
                    self._retry_count += 1
                await asyncio.sleep(last_delay)

        with self._lock:
            self._failure_count += 1
            self._total_latency += time.monotonic() - start
        raise last_exception  # type: ignore[misc]

    def get_retry_count(self) -> int:
        """Return the total number of retries performed."""
        with self._lock:
            return self._retry_count

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._retry_count = 0
            self._success_count = 0
            self._failure_count = 0
            self._total_latency = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the retry engine."""
        with self._lock:
            total = self._success_count + self._failure_count
            avg_latency = (
                self._total_latency / total if total > 0 else 0.0
            )
            return {
                "max_retries": self._max_retries,
                "base_delay": self._base_delay,
                "max_delay": self._max_delay,
                "jitter": self._jitter,
                "retry_count": self._retry_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "total_attempts": total,
                "avg_latency_s": avg_latency,
            }

    # ── Internal ──

    def _compute_delay(self, attempt: int, last_delay: float) -> float:
        """Compute next delay using decorrelated jitter.

        Args:
            attempt: The current attempt number (0-based).
            last_delay: The previous delay in seconds.

        Returns:
            The computed delay in seconds.
        """
        exponential = min(
            self._base_delay * (2**attempt),
            self._max_delay,
        )
        if self._jitter > 0:
            new_delay = min(
                self._max_delay,
                random.uniform(
                    self._base_delay,
                    last_delay * 3.0 + self._base_delay,
                ),
            )
            return new_delay * (1.0 + self._jitter * (random.random() - 0.5))
        return exponential

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"AdaptiveRetryEngine(retries={self._retry_count}, "
                f"success={self._success_count}, fail={self._failure_count})"
            )