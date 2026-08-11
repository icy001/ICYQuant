"""Execution Controller — Runtime controller for execution flow.

Manages the execution control plane, including throttling, concurrency
limits, and graceful degradation during high load.

Responsibilities:
    - Concurrency control (max concurrent executions)
    - Rate limiting for child order dispatch
    - Circuit breaker for broker connections
    - Graceful shutdown coordination

Usage::

    controller = ExecutionController(max_concurrent=10, rate_limit=100)
    await controller.acquire()
    try:
        await dispatch(child_order)
    finally:
        controller.release()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    """Rate limiter state using sliding window."""

    max_rate: float  # Max operations per second
    window_size: float = 1.0  # Window in seconds
    _timestamps: deque[float] = field(default_factory=deque)

    def allow(self) -> bool:
        """Check if an operation is allowed under the rate limit.

        Returns:
            True if allowed, False if rate limited
        """
        now = time.monotonic()
        # Remove expired timestamps
        cutoff = now - self.window_size
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        if len(self._timestamps) < self.max_rate:
            self._timestamps.append(now)
            return True
        return False

    @property
    def current_rate(self) -> float:
        """Current observed rate in ops/sec."""
        now = time.monotonic()
        cutoff = now - self.window_size
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) / self.window_size


class ExecutionController:
    """Runtime execution controller.

    Controls execution flow with concurrency limits, rate limiting,
    and circuit breaker protection.

    Attributes:
        max_concurrent: Maximum concurrent execution tasks
        rate_limit_per_sec: Maximum child order dispatch rate
        active_count: Current active execution count
        rate_limiter: Rate limiter for dispatch operations
        _lock: Async lock for concurrency control
        _semaphore: Semaphore for concurrent task limiting
    """

    def __init__(
        self,
        max_concurrent: int = 50,
        rate_limit_per_sec: float = 100.0,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.rate_limit_per_sec = rate_limit_per_sec
        self.active_count = 0
        self.rate_limiter = RateLimitState(max_rate=rate_limit_per_sec)
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Circuit breaker
        self._failure_count = 0
        self._failure_threshold = 5
        self._circuit_open = False
        self._circuit_reset_time = 0.0
        self._circuit_timeout = 30.0  # seconds

    # ── Concurrency Control ────────────────────────────────────────

    async def acquire(self) -> bool:
        """Acquire a concurrency slot.

        Blocks until a slot is available or circuit is open.

        Returns:
            True if acquired, False if circuit breaker is open
        """
        if self._circuit_open:
            elapsed = time.monotonic() - self._circuit_reset_time
            if elapsed > self._circuit_timeout:
                self._circuit_open = False
                self._failure_count = 0
                logger.info("Circuit breaker reset after %.1fs", elapsed)
            else:
                return False

        await self._semaphore.acquire()
        async with self._lock:
            self.active_count += 1
        return True

    def release(self) -> None:
        """Release a concurrency slot."""
        async def _release():
            async with self._lock:
                self.active_count = max(0, self.active_count - 1)
            self._semaphore.release()
        asyncio.ensure_future(_release())

    async def active_count_now(self) -> int:
        """Get current active execution count."""
        async with self._lock:
            return self.active_count

    # ── Rate Limiting ──────────────────────────────────────────────

    def allow_dispatch(self) -> bool:
        """Check if a child order dispatch is allowed.

        Returns:
            True if dispatch is allowed under rate limit
        """
        return self.rate_limiter.allow()

    async def throttle_dispatch(self) -> None:
        """Wait until dispatch is allowed by rate limiter."""
        while not self.allow_dispatch():
            await asyncio.sleep(0.01)

    # ── Circuit Breaker ────────────────────────────────────────────

    def record_failure(self) -> None:
        """Record a dispatch failure for circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._circuit_open = True
            self._circuit_reset_time = time.monotonic()
            logger.warning(
                "Circuit breaker opened after %d failures",
                self._failure_count,
            )

    def record_success(self) -> None:
        """Record a successful dispatch, resetting failure count."""
        self._failure_count = 0

    @property
    def is_circuit_open(self) -> bool:
        """Whether the circuit breaker is currently open."""
        return self._circuit_open

    @property
    def current_rate(self) -> float:
        """Current observed dispatch rate."""
        return self.rate_limiter.current_rate

    # ── State ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize controller state."""
        return {
            "max_concurrent": self.max_concurrent,
            "rate_limit_per_sec": self.rate_limit_per_sec,
            "active_count": self.active_count,
            "current_rate": self.current_rate,
            "circuit_open": self._circuit_open,
            "failure_count": self._failure_count,
        }
