"""Tool Retry — exponential backoff retry logic for failed tool calls.

Pipeline:
    Tool Execution Failure
        -> RetryPolicy.evaluate()
        -> Should Retry? (check attempt count, error type, backoff)
        -> Wait (exponential backoff + jitter)
        -> Re-execute
        -> Success or Final Failure
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.ai_agent.tooling.tool_result import ToolResult

logger = logging.getLogger(__name__)


# ── Enums ──

class RetryStrategy(str, Enum):
    """Retry backoff strategy."""

    FIXED = "fixed"  # Fixed delay between retries
    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff
    IMMEDIATE = "immediate"  # Retry immediately


# ── RetryPolicy ──

@dataclass
class RetryPolicy:
    """Configuration for tool retry behavior."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter: bool = True
    jitter_factor: float = 0.1

    # ── Retryable Errors ──
    retry_on_timeout: bool = True
    retry_on_runtime_error: bool = True
    retry_on_validation_error: bool = False
    retry_on_permission_error: bool = False

    # ── Rate Limiting ──
    respect_retry_after: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Calculate the delay before the next retry.

        Args:
            attempt: The current attempt number (1-based).

        Returns:
            Delay in seconds.
        """
        if self.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay_seconds
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay_seconds * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay_seconds * (2 ** (attempt - 1))
        else:
            delay = self.base_delay_seconds

        delay = min(delay, self.max_delay_seconds)

        if self.jitter:
            jitter_amount = delay * self.jitter_factor * random.random()
            delay = delay + jitter_amount

        return delay

    def should_retry(self, attempt: int, error_type: str) -> bool:
        """Determine if a retry should be attempted.

        Args:
            attempt: Current attempt number (1-based).
            error_type: The error classification.

        Returns:
            True if retry should proceed.
        """
        if attempt >= self.max_attempts:
            return False

        retryable_map = {
            "timeout": self.retry_on_timeout,
            "runtime": self.retry_on_runtime_error,
            "validation": self.retry_on_validation_error,
            "permission": self.retry_on_permission_error,
        }

        return retryable_map.get(error_type, False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "max_attempts": self.max_attempts,
            "strategy": self.strategy.value,
            "base_delay_seconds": self.base_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "jitter": self.jitter,
            "retry_on_timeout": self.retry_on_timeout,
            "retry_on_runtime_error": self.retry_on_runtime_error,
            "retry_on_validation_error": self.retry_on_validation_error,
            "retry_on_permission_error": self.retry_on_permission_error,
        }


# ── RetryContext ──

@dataclass
class RetryContext:
    """Tracks the state of a retry sequence."""

    tool_name: str
    policy: RetryPolicy
    attempt: int = 0
    total_delay_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def attempts_remaining(self) -> int:
        return max(0, self.policy.max_attempts - self.attempt)


# ── ToolRetry ──

class ToolRetry:
    """Retry manager with configurable backoff strategies.

    Wraps tool execution with retry logic using exponential backoff,
    jitter, and error-type filtering.

    Supports:
        - Fixed, exponential, linear, and immediate backoff
        - Jitter for distributed coordination
        - Error-type filtering (retry only on certain errors)
        - Retry-after header respect
        - Retry context tracking
        - Max delay caps

    Usage:
        retry = ToolRetry()
        result = await retry.execute_with_retry(
            tool_name="backtest.run",
            policy=RetryPolicy(max_attempts=3),
            executor_fn=lambda: tool_executor.execute("backtest.run", params),
        )
    """

    def __init__(self) -> None:
        """Initialize the retry manager."""
        self._initialized: bool = False
        logger.info("ToolRetry created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the retry manager."""
        self._initialized = True
        logger.info("ToolRetry initialized")

    async def shutdown(self) -> None:
        """Shutdown the retry manager."""
        self._initialized = False
        logger.info("ToolRetry shutdown complete")

    # ── Retry Execution ──

    async def execute_with_retry(
        self,
        tool_name: str,
        policy: RetryPolicy,
        executor_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool with retry logic.

        Args:
            tool_name: The tool name.
            policy: The retry policy.
            executor_fn: Async callable that returns a ToolResult.
            *args: Positional args for executor_fn.
            **kwargs: Keyword args for executor_fn.

        Returns:
            The final ToolResult (success or last failure).
        """
        ctx = RetryContext(tool_name=tool_name, policy=policy)

        for attempt in range(1, policy.max_attempts + 1):
            ctx.attempt = attempt

            # Execute
            try:
                result = await executor_fn(*args, **kwargs)
            except Exception as e:
                result = ToolResult.error_result(
                    tool_name=tool_name,
                    error=str(e),
                    error_type="runtime",
                )

            result.attempt = attempt
            result.max_attempts = policy.max_attempts

            # Success
            if result.success:
                if attempt > 1:
                    result.was_retried = True
                    logger.info(
                        f"Retry succeeded for {tool_name}: attempt {attempt}/{policy.max_attempts}"
                    )
                return result

            # Record error
            ctx.errors.append(result.error or "Unknown error")

            # Check if should retry
            if not policy.should_retry(attempt, result.error_type):
                logger.warning(
                    f"Retry not allowed for {tool_name}: "
                    f"error_type={result.error_type}, attempt={attempt}"
                )
                result.was_retried = attempt > 1
                return result

            # Calculate and apply delay
            delay = policy.calculate_delay(attempt)
            ctx.total_delay_seconds += delay

            logger.warning(
                f"Retry {attempt}/{policy.max_attempts} for {tool_name}: "
                f"error='{result.error}', waiting {delay:.2f}s"
            )

            await asyncio.sleep(delay)

        # All attempts exhausted
        result.was_retried = True
        logger.error(
            f"All {policy.max_attempts} retries exhausted for {tool_name}: "
            f"errors={ctx.errors}"
        )
        return result

    async def execute_with_default_retry(
        self,
        tool_name: str,
        executor_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute with a sensible default retry policy.

        Args:
            tool_name: The tool name.
            executor_fn: Async callable that returns a ToolResult.
            *args: Positional args.
            **kwargs: Keyword args.

        Returns:
            The ToolResult.
        """
        default_policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter=True,
        )
        return await self.execute_with_retry(tool_name, default_policy, executor_fn, *args, **kwargs)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get retry manager status."""
        return {
            "initialized": self._initialized,
        }
