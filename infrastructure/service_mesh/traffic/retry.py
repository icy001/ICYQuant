"""Retry management for ICYQuant Service Mesh.

Provides ``RetryManager`` with immediate, exponential, adaptive,
and jitter-based retry strategies, protecting against retry storms
and cascading failures.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RetryStrategy:
    """Retry strategy types."""

    IMMEDIATE = "immediate"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"
    JITTER = "jitter"


class RetryManager:
    """Manages retry logic for requests."""

    def __init__(
        self,
        max_retries: int = 2,
        initial_backoff_ms: int = 100,
        max_backoff_ms: int = 5000,
        backoff_multiplier: float = 2.0,
        strategy: str = RetryStrategy.EXPONENTIAL,
        per_try_timeout_ms: int = 5000,
    ) -> None:
        self._max_retries = max_retries
        self._initial_backoff_ms = initial_backoff_ms
        self._max_backoff_ms = max_backoff_ms
        self._backoff_multiplier = backoff_multiplier
        self._strategy = strategy
        self._per_try_timeout_ms = per_try_timeout_ms
        self._lock = threading.RLock()
        self._retry_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_latency = 0.0
        self._recent_success_rates: Dict[str, List[float]] = {}

    def compute_backoff(
        self, attempt: int, target: str = ""
    ) -> float:
        """Compute backoff time for a given attempt."""
        base = self._initial_backoff_ms / 1000.0

        if self._strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif self._strategy == RetryStrategy.JITTER:
            jitter = random.uniform(0, base * 0.5)
            return min(
                base + jitter,
                self._max_backoff_ms / 1000.0,
            )
        elif self._strategy == RetryStrategy.ADAPTIVE:
            success_rates = self._recent_success_rates.get(
                target, [1.0]
            )
            avg_rate = (
                sum(success_rates) / len(success_rates)
                if success_rates
                else 1.0
            )
            if avg_rate > 0.9:
                multiplier = self._backoff_multiplier
            elif avg_rate > 0.7:
                multiplier = self._backoff_multiplier * 0.5
            else:
                multiplier = self._backoff_multiplier * 0.25
            return min(
                base * (multiplier ** attempt),
                self._max_backoff_ms / 1000.0,
            )
        else:
            # Exponential
            return min(
                base * (self._backoff_multiplier ** attempt),
                self._max_backoff_ms / 1000.0,
            )

    def should_retry(
        self,
        attempt: int,
        status_code: int = 0,
        error_type: str = "",
    ) -> bool:
        """Determine if a request should be retried."""
        if attempt >= self._max_retries:
            return False
        if status_code > 0 and 200 <= status_code < 400:
            return False
        return True

    def record_attempt(
        self,
        target: str,
        success: bool,
        latency_s: float = 0.0,
    ) -> None:
        with self._lock:
            self._retry_count += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
            self._total_latency += latency_s

            if target not in self._recent_success_rates:
                self._recent_success_rates[target] = []
            self._recent_success_rates[target].append(
                1.0 if success else 0.0
            )
            rates = self._recent_success_rates[target]
            if len(rates) > 20:
                self._recent_success_rates[target] = rates[-20:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = (
                self._success_count + self._failure_count
            )
            return {
                "strategy": self._strategy,
                "max_retries": self._max_retries,
                "retry_count": self._retry_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "success_rate": (
                    self._success_count / total
                    if total > 0
                    else 0.0
                ),
                "avg_latency_s": (
                    self._total_latency / total
                    if total > 0
                    else 0.0
                ),
            }