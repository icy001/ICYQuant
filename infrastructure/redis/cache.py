"""
Production cache service.

Provides a unified cache API with namespace
management, serialization, TTL support, and
batch operations.
"""

from __future__ import annotations

from typing import Any, Optional

from .client import RedisClient
from .serializer import JsonSerializer
from .exceptions import (
    CacheOperationError,
)


class CacheService:
    """
    Production cache service.

    Wraps Redis client with namespace management,
    automatic serialization, and batch operations.
    All business code should use this service
    instead of direct Redis client calls.
    """

    def __init__(
        self,
        client: RedisClient,
        namespace: str = "icyquant",
    ) -> None:

        self._client = client

        self._namespace = namespace

    def key(
        self,
        key: str,
    ) -> str:
        """
        Build namespaced key.

        Args:
            key: Original key name.

        Returns:
            Namespaced key (namespace:key).
        """

        return (
            f"{self._namespace}:{key}"
        )

    async def get(
        self,
        key: str,
    ) -> Optional[Any]:
        """
        Get value by key.

        Args:
            key: Cache key.

        Returns:
            Deserialized value or None if not found.
        """

        value = await self._client.client.get(
            self.key(key)
        )

        if value is None:
            return None

        return JsonSerializer.loads(value)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set key-value pair.

        Args:
            key: Cache key.
            value: Value to store (will be serialized).
            ttl: Time-to-live in seconds (optional).

        Raises:
            CacheOperationError: If set operation fails.
        """

        payload = JsonSerializer.dumps(value)

        ok = await self._client.client.set(
            self.key(key),
            payload,
            ex=ttl,
        )

        if not ok:
            raise CacheOperationError(
                f"Failed to set '{key}'."
            )

    async def delete(
        self,
        key: str,
    ) -> int:
        """
        Delete key.

        Args:
            key: Cache key.

        Returns:
            Number of keys deleted.
        """

        return await self._client.client.delete(
            self.key(key)
        )

    async def exists(
        self,
        key: str,
    ) -> bool:
        """
        Check if key exists.

        Args:
            key: Cache key.

        Returns:
            True if key exists, False otherwise.
        """

        return bool(
            await self._client.client.exists(
                self.key(key)
            )
        )

    async def expire(
        self,
        key: str,
        ttl: int,
    ) -> bool:
        """
        Set TTL on existing key.

        Args:
            key: Cache key.
            ttl: Time-to-live in seconds.

        Returns:
            True if TTL was set, False if key doesn't exist.
        """

        return await self._client.client.expire(
            self.key(key),
            ttl,
        )

    async def mget(
        self,
        *keys: str,
    ) -> list[Optional[Any]]:
        """
        Get multiple values by keys.

        Args:
            *keys: Multiple cache keys.

        Returns:
            List of deserialized values (None for missing keys).
        """

        values = await self._client.client.mget(
            *[
                self.key(k)
                for k in keys
            ]
        )

        result: list[Optional[Any]] = []

        for item in values:

            if item is None:
                result.append(None)

            else:
                result.append(
                    JsonSerializer.loads(item)
                )

        return result

    async def mset(
        self,
        mapping: dict[str, Any],
    ) -> None:
        """
        Set multiple key-value pairs.

        Args:
            mapping: Dictionary of key-value pairs.
        """

        payload = {
            self.key(k): JsonSerializer.dumps(v)
            for k, v in mapping.items()
        }

        await self._client.client.mset(
            payload
        )