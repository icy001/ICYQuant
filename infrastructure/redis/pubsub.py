"""
Redis Pub/Sub service.

Provides publish/subscribe messaging
capabilities with handler-based consumption.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict

from .client import RedisClient


MessageHandler = Callable[
    [Dict[str, Any]],
    Awaitable[None],
]


class PubSubService:
    """
    Redis Pub/Sub service.

    Encapsulates Redis Pub/Sub operations
    with a clean interface for publishing
    messages and consuming them via handlers.
    """

    def __init__(
        self,
        client: RedisClient,
    ) -> None:

        self._client = client

    async def publish(
        self,
        channel: str,
        message: str,
    ) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name.
            message: Message payload (string).

        Returns:
            Number of receivers that got the message.
        """

        return await self._client.client.publish(
            channel,
            message,
        )

    async def subscribe(
        self,
        *channels: str,
    ):
        """
        Subscribe to channels.

        Args:
            *channels: Channel names to subscribe to.

        Returns:
            PubSub object for message consumption.
        """

        pubsub = self._client.client.pubsub()

        await pubsub.subscribe(*channels)

        return pubsub

    async def consume(
        self,
        pubsub: Any,
        handler: MessageHandler,
    ) -> None:
        """
        Consume messages from PubSub.

        Args:
            pubsub: PubSub object from subscribe().
            handler: Async callback for each message.
        """

        async for message in pubsub.listen():

            if message["type"] != "message":
                continue

            await handler(message)