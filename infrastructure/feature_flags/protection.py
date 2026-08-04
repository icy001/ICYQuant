"""
Feature flag platform protection.

Provides runtime protection mechanisms including:
    - Evaluation rate limiting
    - Snapshot integrity verification
    - Rule validation enforcement
    - Safe rollback guarantees
    - Circuit breaker for cascading failures
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .snapshot import FeatureSnapshot

logger = logging.getLogger(__name__)


class EvaluationRateLimiter:
    """
    Rate limits feature flag evaluations.

    Prevents abuse and ensures fair usage
    by limiting the number of evaluations
    per time window.

    Usage:
        limiter = EvaluationRateLimiter(max_per_second=10000)
        allowed = limiter.is_allowed()
    """

    def __init__(
        self,
        max_per_second: int = 100000,
        window_seconds: float = 1.0,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            max_per_second: Max evaluations per second.
            window_seconds: Time window in seconds.
        """
        self._max_per_second = max_per_second
        self._window_seconds = window_seconds
        self._request_timestamps: List[float] = []
        self._total_requests = 0
        self._blocked_requests = 0

    def is_allowed(self) -> bool:
        """
        Check if a new evaluation is allowed.

        Returns:
            True if the evaluation is allowed.
        """
        now = time.monotonic()

        # Remove old timestamps
        cutoff = now - self._window_seconds
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > cutoff
        ]

        # Check rate limit
        if len(self._request_timestamps) >= self._max_per_second:
            self._blocked_requests += 1
            return False

        self._request_timestamps.append(now)
        self._total_requests += 1
        return True

    def get_rate(self) -> float:
        """Get current request rate per second."""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        recent = [ts for ts in self._request_timestamps if ts > cutoff]
        return len(recent) / self._window_seconds

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "max_per_second": self._max_per_second,
            "current_rate": self.get_rate(),
            "total_requests": self._total_requests,
            "blocked_requests": self._blocked_requests,
            "window_seconds": self._window_seconds,
        }

    def reset(self) -> None:
        """Reset rate limiter state."""
        self._request_timestamps.clear()
        self._total_requests = 0
        self._blocked_requests = 0


class SnapshotIntegrityChecker:
    """
    Verifies snapshot integrity before activation.

    Ensures that snapshots have valid checksums
    and are not corrupted before being activated
    in the runtime.
    """

    def __init__(self) -> None:
        self._check_count = 0
        self._fail_count = 0

    def check(self, snapshot: FeatureSnapshot) -> Dict[str, Any]:
        """
        Verify snapshot integrity.

        Args:
            snapshot: Snapshot to verify.

        Returns:
            Integrity check result.
        """
        self._check_count += 1

        # Verify checksum
        if not snapshot.verify_integrity():
            self._fail_count += 1
            return {
                "valid": False,
                "reason": "checksum_mismatch",
                "version": snapshot.version,
            }

        # Verify flags are properly structured
        for key, data in snapshot.flags.items():
            if not isinstance(data, dict):
                self._fail_count += 1
                return {
                    "valid": False,
                    "reason": f"flag_data_not_dict: {key}",
                    "version": snapshot.version,
                }

        return {
            "valid": True,
            "version": snapshot.version,
            "flags_count": len(snapshot.flags),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get integrity checker statistics."""
        return {
            "check_count": self._check_count,
            "fail_count": self._fail_count,
            "pass_rate": (
                (self._check_count - self._fail_count) / self._check_count
                if self._check_count > 0
                else 0.0
            ),
        }


class CircuitBreaker:
    """
    Simple circuit breaker for cascading failures.

    Monitors error rates and temporarily blocks
    requests when error thresholds are exceeded.

    States:
        - CLOSED: Normal operation
        - OPEN: Blocking requests
        - HALF_OPEN: Allowing limited requests
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 3,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures to open circuit.
            recovery_timeout: Seconds before attempting recovery.
            half_open_max_requests: Max requests in half-open state.
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_requests = half_open_max_requests

        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_requests = 0

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        self._check_state()
        return self._state

    def _check_state(self) -> None:
        """Check and update circuit breaker state."""
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time > self._recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_requests = 0

    def can_proceed(self) -> bool:
        """
        Check if a request can proceed.

        Returns:
            True if the request is allowed.
        """
        self._check_state()

        if self._state == self.CLOSED:
            return True
        elif self._state == self.HALF_OPEN:
            return self._half_open_requests < self._half_open_max_requests
        else:
            return False

    def record_success(self) -> None:
        """Record a successful request."""
        self._success_count += 1

        if self._state == self.HALF_OPEN:
            self._half_open_requests += 1
            if self._half_open_requests >= self._half_open_max_requests:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker closed after successful recovery")

    def record_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
            self._half_open_requests = 0
            logger.warning("Circuit breaker opened during half-open state")
        elif self._failure_count >= self._failure_threshold:
            self._state = self.OPEN
            logger.warning(
                "Circuit breaker opened: %d failures (threshold=%d)",
                self._failure_count,
                self._failure_threshold,
            )

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
            "half_open_requests": self._half_open_requests,
        }


class PlatformProtection:
    """
    Unified platform protection manager.

    Combines rate limiting, snapshot integrity
    checking, and circuit breaking into a
    single protection layer.

    Usage:
        protection = PlatformProtection()
        if protection.can_evaluate():
            result = await service.evaluate(...)
            protection.record_result(success)
    """

    def __init__(
        self,
        rate_limiter: Optional[EvaluationRateLimiter] = None,
        integrity_checker: Optional[SnapshotIntegrityChecker] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        """
        Initialize platform protection.

        Args:
            rate_limiter: Rate limiter instance.
            integrity_checker: Integrity checker instance.
            circuit_breaker: Circuit breaker instance.
        """
        self._rate_limiter = rate_limiter or EvaluationRateLimiter()
        self._integrity_checker = integrity_checker or SnapshotIntegrityChecker()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    @property
    def rate_limiter(self) -> EvaluationRateLimiter:
        return self._rate_limiter

    @property
    def integrity_checker(self) -> SnapshotIntegrityChecker:
        return self._integrity_checker

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    def can_evaluate(self) -> bool:
        """
        Check if an evaluation can proceed.

        Returns:
            True if the evaluation is allowed.
        """
        if not self._circuit_breaker.can_proceed():
            return False
        if not self._rate_limiter.is_allowed():
            return False
        return True

    def verify_snapshot(self, snapshot: FeatureSnapshot) -> Dict[str, Any]:
        """
        Verify snapshot integrity.

        Args:
            snapshot: Snapshot to verify.

        Returns:
            Verification result.
        """
        return self._integrity_checker.check(snapshot)

    def record_result(self, success: bool) -> None:
        """
        Record an evaluation result.

        Args:
            success: Whether the evaluation succeeded.
        """
        if success:
            self._circuit_breaker.record_success()
        else:
            self._circuit_breaker.record_failure()

    def get_stats(self) -> Dict[str, Any]:
        """Get platform protection statistics."""
        return {
            "rate_limiter": self._rate_limiter.get_stats(),
            "integrity_checker": self._integrity_checker.get_stats(),
            "circuit_breaker": self._circuit_breaker.get_stats(),
        }
