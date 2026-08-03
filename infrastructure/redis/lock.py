"""
Distributed lock.

Provides distributed locking capabilities
using Redis for coordination across
multiple service instances.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from .client import RedisClient
from .exceptions import (
    DistributedLockError,
)


class DistributedLock:
    """
    Distributed lock manager.

    Provides atomic locking across multiple
    service instances using Redis. Supports
    automatic lock release and timeout.
    """

    def __init__(
        self,
        client: RedisClient,
    ) -> None:

        self._client = client

    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        timeout: int = 30,
    ):
        """
        Acquire distributed lock.

        Args:
            key: Lock key name.
            timeout: Lock timeout in seconds.

        Yields:
            None (context manager).

        Raises:
            DistributedLockError: If lock cannot be acquired.

        Example:
            async with lock.acquire("order:123"):
                await process_order()
        """

        lock = self._client.client.lock(
            key,
            timeout=timeout,
        )

        acquired = await lock.acquire()

        if not acquired:
            raise DistributedLockError(
                f"Unable to acquire lock '{key}'."
            )

        try:

            yield

        finally:

            try:
                await lock.release()
            except Exception:
                # Lock may have expired
                pass