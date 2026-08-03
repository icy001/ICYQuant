"""
Retry policy for storage operations.

Provides configurable retry behavior for
storage operations with exponential backoff,
ensuring resilience against transient failures.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Type,
    TypeVar,
)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def storage_retry(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    jitter: bool = True,
    exceptions: Optional[tuple] = None,
) -> Callable[[F], F]:
    """
    Retry decorator for storage operations.

    Provides exponential backoff with jitter for
    storage operations, retrying on specified
    exception types.

    Args:
        max_attempts: Maximum number of attempts.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential: Use exponential backoff.
        jitter: Add random jitter to delay.
        exceptions: Exception types to retry on.
            Default: all exceptions.

    Returns:
        Decorator function.

    Usage:
        @storage_retry(max_attempts=3)
        async def upload(self, key, data):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc

                    # Check if exception should be retried
                    if exceptions and not isinstance(
                        exc, exceptions
                    ):
                        raise

                    # Don't sleep after last attempt
                    if attempt == max_attempts:
                        break

                    # Calculate delay
                    if exponential:
                        delay = min(
                            base_delay
                            * (2 ** (attempt - 1)),
                            max_delay,
                        )
                    else:
                        delay = base_delay

                    if jitter:
                        import random

                        delay *= (
                            0.5 + random.random() * 0.5
                        )

                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


class StorageRetryConfig:
    """
    Retry configuration for storage operations.

    Encapsulates retry parameters and provides
    a pre-configured decorator.

    Attributes:
        max_attempts: Maximum number of attempts.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential: Use exponential backoff.
        jitter: Add random jitter.
        exceptions: Exception types to retry on.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential: bool = True,
        jitter: bool = True,
        exceptions: Optional[tuple] = None,
    ) -> None:

        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential
        self.jitter = jitter
        self.exceptions = exceptions

    def __call__(
        self,
        func: F,
    ) -> F:
        """
        Apply retry decorator to a function.

        Args:
            func: Async function to wrap.

        Returns:
            Wrapped function with retry logic.
        """

        return storage_retry(
            max_attempts=self.max_attempts,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential=self.exponential,
            jitter=self.jitter,
            exceptions=self.exceptions,
        )(func)

    def decorator(
        self,
    ) -> Callable[[F], F]:
        """
        Get the retry decorator.

        Returns:
            Retry decorator function.
        """

        return storage_retry(
            max_attempts=self.max_attempts,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential=self.exponential,
            jitter=self.jitter,
            exceptions=self.exceptions,
        )


# Default retry config for storage operations
default_retry = StorageRetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    exponential=True,
    jitter=True,
)

# Retry config for critical operations
critical_retry = StorageRetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    exponential=True,
    jitter=True,
)

# Retry config for non-critical operations
lenient_retry = StorageRetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    exponential=True,
    jitter=True,
)