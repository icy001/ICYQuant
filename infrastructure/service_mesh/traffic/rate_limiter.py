"""Rate limiter for ICYQuant Service Mesh.

Provides ``RateLimiter`` with token bucket, leaky bucket, and
sliding window strategies, supporting global/per-service/per-client
rate limiting with adaptive adjustment.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RateLimitStrategy:
    """Rate limiting strategy types."""

    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    SLIDING_WINDOW = "sliding_window"


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(
        self, rate: float, burst: int
    ) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = burst
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            refill = elapsed * self._rate
            self._tokens = min(
                self._burst,
                self._tokens + refill,
            )
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    @property
    def available_tokens(self) -> float:
        with self._lock:
            return self._tokens


class LeakyBucket:
    """Leaky bucket rate limiter."""

    def __init__(
        self, rate: float, capacity: int
    ) -> None:
        self._rate = rate
        self._capacity = capacity
        self._queue: List[float] = []
        self._last_leak = time.monotonic()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_leak
            leak_amount = elapsed * self._rate
            self._last_leak = now

            # Process leaks
            while leak_amount >= 1.0 and self._queue:
                self._queue.pop(0)
                leak_amount -= 1.0

            if len(self._queue) < self._capacity:
                self._queue.append(now)
                return True
            return False

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return len(self._queue)


class SlidingWindow:
    """Sliding window rate limiter."""

    def __init__(
        self, rate: float, window_s: float = 1.0
    ) -> None:
        self._rate = rate
        self._window_s = window_s
        self._timestamps: List[float] = []
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._window_s
            self._timestamps = [
                t for t in self._timestamps if t >= cutoff
            ]
            if len(self._timestamps) < self._rate * self._window_s:
                self._timestamps.append(now)
                return True
            return False

    @property
    def current_count(self) -> int:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._window_s
            return len(
                [t for t in self._timestamps if t >= cutoff]
            )


class RateLimiter:
    """Unified rate limiter."""

    def __init__(
        self,
        strategy: str = RateLimitStrategy.TOKEN_BUCKET,
        default_rate: float = 100.0,
        default_burst: int = 200,
    ) -> None:
        self._strategy = strategy
        self._default_rate = default_rate
        self._default_burst = default_burst
        self._lock = threading.RLock()
        self._limiters: Dict[str, Any] = {}
        self._global_limiter = self._create_limiter(
            default_rate, default_burst
        )
        self._allowed_count = 0
        self._blocked_count = 0

    def _create_limiter(
        self, rate: float, burst: int
    ) -> Any:
        if self._strategy == RateLimitStrategy.LEAKY_BUCKET:
            return LeakyBucket(rate, burst)
        elif self._strategy == RateLimitStrategy.SLIDING_WINDOW:
            return SlidingWindow(rate, burst / max(rate, 1.0))
        else:
            return TokenBucket(rate, burst)

    def configure(
        self,
        key: str,
        rate: Optional[float] = None,
        burst: Optional[int] = None,
    ) -> None:
        with self._lock:
            r = rate or self._default_rate
            b = burst or self._default_burst
            self._limiters[key] = self._create_limiter(r, b)

    def try_acquire(
        self,
        key: str = "",
        global_scope: bool = True,
    ) -> bool:
        """Try to acquire a rate limit permit."""
        with self._lock:
            limiter = self._limiters.get(key) if key else None
            if key and limiter is None:
                limiter = self._create_limiter(
                    self._default_rate, self._default_burst
                )
                self._limiters[key] = limiter

        # Check global limit
        if global_scope:
            if not self._global_limiter.try_acquire():
                with self._lock:
                    self._blocked_count += 1
                return False

        # Check per-key limit
        if limiter:
            if not limiter.try_acquire():
                with self._lock:
                    self._blocked_count += 1
                return False

        with self._lock:
            self._allowed_count += 1
        return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "limiter_count": len(self._limiters),
                "allowed_count": self._allowed_count,
                "blocked_count": self._blocked_count,
                "global_rate": self._default_rate,
                "global_burst": self._default_burst,
            }