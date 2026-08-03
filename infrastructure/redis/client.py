"""
Async Redis client.

Production-grade async Redis client
with connection pooling, lifecycle management,
pipeline support, and runtime statistics.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from typing import Optional

from .config import RedisConfig
from .exceptions import (
    RedisConnectionError,
)


class RedisClient:
    """
    Production Redis client.

    Manages async Redis connections with
    connection pooling, automatic reconnection,
    pipeline batching, and runtime monitoring.
    """

    def __init__(
        self,
        config: RedisConfig,
    ) -> None:

        self._config = config

        self._pool: Optional[object] = None

        self._client: Optional[object] = None

        self._created_at: Optional[float] = None

    @property
    def client(
        self,
    ):
        """
        Return the async Redis client.

        Raises RedisConnectionError if the
        client has not been initialized.
        """

        if self._client is None:
            raise RedisConnectionError(
                "Redis client has not been initialized. "
                "Call startup() first."
            )

        return self._client

    @property
    def config(
        self,
    ) -> RedisConfig:
        """
        Return the Redis configuration.
        """

        return self._config

    @property
    def is_initialized(
        self,
    ) -> bool:
        """
        Check if the client has been initialized.
        """

        return self._client is not None

    async def startup(
        self,
    ) -> None:
        """
        Initialize Redis connection pool and client.

        Creates the connection pool, instantiates
        the Redis client, and verifies connectivity
        with a PING command.
        """

        try:
            from redis.asyncio import Redis
            from redis.asyncio.connection import (
                ConnectionPool,
            )

        except ImportError:
            raise RedisConnectionError(
                "redis-py is not installed. "
                "Install with: pip install redis[hiredis]"
            )

        self._pool = ConnectionPool.from_url(

            self._config.url(),

            max_connections=(
                self._config.max_connections
            ),

            socket_timeout=(
                self._config.socket_timeout
            ),

            socket_connect_timeout=(
                self._config.socket_connect_timeout
            ),

            decode_responses=(
                self._config.decode_responses
            ),

            health_check_interval=(
                self._config.health_check_interval
            ),

        )

        self._client = Redis(
            connection_pool=self._pool
        )

        await self._client.ping()

        self._created_at = perf_counter()

    async def shutdown(
        self,
    ) -> None:
        """
        Disconnect client and connection pool.

        Gracefully releases all connections and
        clears the client and pool references.
        """

        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass

        if self._pool is not None:
            try:
                await self._pool.disconnect()
            except Exception:
                pass

        self._client = None

        self._pool = None

        self._created_at = None

    @asynccontextmanager
    async def pipeline(
        self,
    ):
        """
        Create a Redis pipeline context manager.

        Batches multiple Redis commands into a
        single network round-trip for efficiency.
        Automatically executes on success and
        resets on failure.

        Yields:
            Redis pipeline object.

        Example:
            async with redis.pipeline() as pipe:
                await pipe.set("key1", "val1")
                await pipe.set("key2", "val2")
        """

        pipe = self.client.pipeline()

        try:

            yield pipe

            await pipe.execute()

        except Exception:

            try:
                await pipe.reset()
            except Exception:
                pass

            raise

    async def ping(
        self,
    ) -> float:
        """
        Execute PING command and measure latency.

        Returns:
            Round-trip latency in milliseconds.
        """

        start = perf_counter()

        await self.client.ping()

        return (
            perf_counter() - start
        ) * 1000

    def statistics(
        self,
    ) -> dict[str, object]:
        """
        Return runtime statistics.

        Provides connection pool and client
        status information for monitoring.
        """

        return {
            "initialized": (
                self._client is not None
            ),
            "max_connections": (
                self._config.max_connections
            ),
            "socket_timeout": (
                self._config.socket_timeout
            ),
            "socket_connect_timeout": (
                self._config.socket_connect_timeout
            ),
            "health_check_interval": (
                self._config.health_check_interval
            ),
            "uptime_seconds": (
                None
                if self._created_at is None
                else round(
                    perf_counter()
                    - self._created_at,
                    3,
                )
            ),
        }