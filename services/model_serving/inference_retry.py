"""
ICYQuant Inference Retry — Exponential backoff retry for inference calls.

Provides intelligent retry logic for inference failures:
  - Exponential backoff with jitter
  - Configurable retry policies per model
  - Error classification (retryable vs non-retryable)
  - Retry budget management
  - Retry metrics tracking
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class RetryDecision(str, Enum):
    """Decision after an inference failure."""
    RETRY = "retry"
    FAIL_FAST = "fail_fast"
    CIRCUIT_OPEN = "circuit_open"


class RetryableErrorType(str, Enum):
    """Classification of error types."""
    TIMEOUT = "timeout"
    TRANSIENT = "transient"         # Temporary network/connection issues
    OVERLOADED = "overloaded"       # Server busy / rate limited
    MODEL_ERROR = "model_error"     # Model-specific error
    VALIDATION = "validation"       # Feature/input validation error
    UNKNOWN = "unknown"


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_retries: int = 3
    base_delay_ms: float = 100.0
    max_delay_ms: float = 5000.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1

    # Which error types to retry
    retryable_errors: Set[RetryableErrorType] = field(default_factory=lambda: {
        RetryableErrorType.TIMEOUT,
        RetryableErrorType.TRANSIENT,
        RetryableErrorType.OVERLOADED,
    })

    # Retry budget
    max_total_retries_per_window: int = 100
    retry_window_seconds: int = 60


@dataclass
class RetryStats:
    """Retry statistics."""
    total_attempts: int = 0
    first_attempt_success: int = 0
    retried_success: int = 0
    retried_failed: int = 0
    retries_by_attempt: Dict[int, int] = field(default_factory=dict)
    total_retry_delay_ms: float = 0.0


# ---------------------------------------------------------------------------
# Default retry policies per tier
# ---------------------------------------------------------------------------

POLICY_REALTIME = RetryPolicy(
    max_retries=1,
    base_delay_ms=10.0,
    max_delay_ms=100.0,
)

POLICY_STANDARD = RetryPolicy(
    max_retries=2,
    base_delay_ms=100.0,
    max_delay_ms=2000.0,
)

POLICY_BATCH = RetryPolicy(
    max_retries=3,
    base_delay_ms=500.0,
    max_delay_ms=30000.0,
)

POLICY_CRITICAL = RetryPolicy(
    max_retries=5,
    base_delay_ms=200.0,
    max_delay_ms=10000.0,
)


# ---------------------------------------------------------------------------
# Error Classifier
# ---------------------------------------------------------------------------

class ErrorClassifier:
    """Classifies inference errors as retryable or not."""

    # Exception types that should be retried
    RETRYABLE_EXCEPTIONS: Set[type] = {
        asyncio.TimeoutError,
        TimeoutError,
        ConnectionError,
        OSError,
    }

    @classmethod
    def classify(cls, exception: Exception) -> RetryableErrorType:
        """Classify an exception into a retryable error type."""
        if isinstance(exception, asyncio.TimeoutError):
            return RetryableErrorType.TIMEOUT

        if isinstance(exception, (ConnectionError, OSError)):
            return RetryableErrorType.TRANSIENT

        error_msg = str(exception).lower()
        if any(kw in error_msg for kw in ("rate limit", "too many", "overloaded", "busy")):
            return RetryableErrorType.OVERLOADED

        if any(kw in error_msg for kw in ("validation", "invalid", "schema")):
            return RetryableErrorType.VALIDATION

        if any(kw in error_msg for kw in ("model", "runtime", "backend")):
            return RetryableErrorType.MODEL_ERROR

        return RetryableErrorType.UNKNOWN

    @classmethod
    def is_retryable(cls, exception: Exception, policy: RetryPolicy) -> bool:
        """Determine if an exception should be retried."""
        error_type = cls.classify(exception)
        return error_type in policy.retryable_errors


# ---------------------------------------------------------------------------
# Retry Executor
# ---------------------------------------------------------------------------

class RetryExecutor:
    """Executes inference calls with exponential backoff retry.

    Usage::

        executor = RetryExecutor()
        result = await executor.execute(
            "nvda_model",
            engine.predict("nvda_model", features),
            policy=POLICY_STANDARD,
        )
    """

    def __init__(self):
        self._initialized = False

        # Per-model policies
        self._policies: Dict[str, RetryPolicy] = {
            "default": POLICY_STANDARD,
        }

        # Per-model stats
        self._stats: Dict[str, RetryStats] = {}

        # Retry budget tracking: model_id → (window_start, count)
        self._retry_budgets: Dict[str, tuple[float, int]] = {}

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RetryExecutor initialized")

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def set_policy(self, model_id: str, policy: RetryPolicy) -> None:
        """Set retry policy for a model."""
        self._policies[model_id] = policy

    def get_policy(self, model_id: str) -> RetryPolicy:
        """Get effective retry policy for a model."""
        return self._policies.get(model_id, self._policies["default"])

    def use_realtime_policy(self, model_id: str) -> None:
        self.set_policy(model_id, POLICY_REALTIME)

    def use_standard_policy(self, model_id: str) -> None:
        self.set_policy(model_id, POLICY_STANDARD)

    def use_batch_policy(self, model_id: str) -> None:
        self.set_policy(model_id, POLICY_BATCH)

    # ------------------------------------------------------------------
    # Execute with retry
    # ------------------------------------------------------------------

    async def execute(
        self,
        model_id: str,
        coro_fn: Callable[[], Coroutine[Any, Any, T]],
        policy: Optional[RetryPolicy] = None,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> T:
        """Execute a coroutine with exponential backoff retry.

        Args:
            model_id: Model identifier.
            coro_fn: Callable that returns a coroutine (recreated each attempt).
            policy: Retry policy override.
            on_retry: Optional callback invoked before each retry.

        Returns:
            Result of the successful attempt.

        Raises:
            The last exception if all retries exhausted.
        """
        effective_policy = policy or self.get_policy(model_id)

        # Stats
        if model_id not in self._stats:
            self._stats[model_id] = RetryStats()
        stats = self._stats[model_id]
        stats.total_attempts += 1

        last_error: Optional[Exception] = None

        for attempt in range(effective_policy.max_retries + 1):
            try:
                # Check retry budget
                if attempt > 0:
                    if not self._check_retry_budget(model_id, effective_policy):
                        logger.warning(
                            "Retry budget exhausted for %s", model_id
                        )
                        raise last_error  # type: ignore[misc]

                result = await coro_fn()

                # Success tracking
                if attempt == 0:
                    stats.first_attempt_success += 1
                else:
                    stats.retried_success += 1
                    stats.retries_by_attempt[attempt] = (
                        stats.retries_by_attempt.get(attempt, 0) + 1
                    )

                return result

            except Exception as exc:
                last_error = exc

                # Should we retry?
                if attempt >= effective_policy.max_retries:
                    stats.retried_failed += 1
                    break

                if not ErrorClassifier.is_retryable(exc, effective_policy):
                    logger.debug(
                        "Non-retryable error for %s: %s", model_id, exc
                    )
                    stats.retried_failed += 1
                    break

                # Compute backoff delay
                delay = effective_policy.base_delay_ms * (
                    effective_policy.backoff_multiplier ** attempt
                )
                delay = min(delay, effective_policy.max_delay_ms)

                # Add jitter
                if effective_policy.jitter:
                    jitter_range = delay * effective_policy.jitter_factor
                    delay += random.uniform(-jitter_range, jitter_range)
                    delay = max(0, delay)

                stats.total_retry_delay_ms += delay

                logger.debug(
                    "Retry %d/%d for %s after %.0fms: %s",
                    attempt + 1, effective_policy.max_retries,
                    model_id, delay, exc,
                )

                if on_retry:
                    try:
                        on_retry(attempt + 1, exc)
                    except Exception:
                        pass

                # Record budget consumption
                self._consume_retry_budget(model_id)

                await asyncio.sleep(delay / 1000.0)

        # All retries exhausted
        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Retry budget
    # ------------------------------------------------------------------

    def _check_retry_budget(self, model_id: str, policy: RetryPolicy) -> bool:
        """Check if retry budget remains for this window."""
        now = time.time()
        budget = self._retry_budgets.get(model_id)

        if budget is None:
            return True

        window_start, count = budget
        if now - window_start > policy.retry_window_seconds:
            # New window
            self._retry_budgets[model_id] = (now, 0)
            return True

        return count < policy.max_total_retries_per_window

    def _consume_retry_budget(self, model_id: str) -> None:
        """Record a retry consumption."""
        now = time.time()
        budget = self._retry_budgets.get(model_id)

        if budget is None:
            self._retry_budgets[model_id] = (now, 1)
            return

        window_start, count = budget
        if now - window_start > 60:  # Reset window
            self._retry_budgets[model_id] = (now, 1)
        else:
            self._retry_budgets[model_id] = (window_start, count + 1)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get retry statistics."""
        if model_id:
            stats = self._stats.get(model_id)
            if stats is None:
                return {}
            return self._format_stats(stats)

        return {
            mid: self._format_stats(s)
            for mid, s in self._stats.items()
        }

    @staticmethod
    def _format_stats(stats: RetryStats) -> Dict[str, Any]:
        total = max(stats.total_attempts, 1)
        return {
            "total_attempts": stats.total_attempts,
            "first_attempt_success": stats.first_attempt_success,
            "first_attempt_success_rate": round(
                stats.first_attempt_success / total, 4
            ),
            "retried_success": stats.retried_success,
            "retried_failed": stats.retried_failed,
            "avg_retry_delay_ms": round(
                stats.total_retry_delay_ms / max(stats.retried_success + stats.retried_failed, 1), 2
            ),
            "retries_by_attempt": stats.retries_by_attempt,
        }

    def get_retry_rate(self, model_id: Optional[str] = None) -> float:
        """Get the retry rate (attempts beyond first / total)."""
        if model_id:
            stats = self._stats.get(model_id)
            if stats is None:
                return 0.0
            total = max(stats.total_attempts, 1)
            return (stats.retried_success + stats.retried_failed) / total

        total_attempts = sum(s.total_attempts for s in self._stats.values())
        total_retries = sum(
            s.retried_success + s.retried_failed
            for s in self._stats.values()
        )
        return total_retries / max(total_attempts, 1)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "policies_registered": len(self._policies),
            "models_tracked": len(self._stats),
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return f"RetryExecutor(policies={len(self._policies)})"

# Need time import
import time
