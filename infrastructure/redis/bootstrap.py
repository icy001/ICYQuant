"""
Redis infrastructure bootstrap.

Provides lifecycle management and integration
with the application bootstrap system.
"""

from __future__ import annotations

from .cache import CacheService
from .client import RedisClient
from .health import RedisHealth
from .lock import DistributedLock
from .metrics import RedisMetrics
from .pubsub import PubSubService
from .stream import StreamService


class RedisBootstrap:
    """
    Redis infrastructure bootstrap.

    Manages the complete Redis infrastructure
    lifecycle including client initialization,
    service creation, and shutdown.
    """

    def __init__(
        self,
        client: RedisClient,
    ) -> None:

        self.client = client

        self.cache = CacheService(client)

        self.lock = DistributedLock(client)

        self.pubsub = PubSubService(client)

        self.stream = StreamService(client)

        self.health = RedisHealth(client)

        self.metrics = RedisMetrics()

    async def startup(
        self,
    ) -> None:
        """
        Initialize Redis infrastructure.

        Starts the Redis client connection
        and verifies connectivity.
        """

        await self.client.startup()

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown Redis infrastructure.

        Gracefully disconnects the Redis client
        and releases all resources.
        """

        await self.client.shutdown()