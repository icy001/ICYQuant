"""
Redis Stream service.

Provides stream-based messaging with
consumer groups, message acknowledgment,
and reliable event processing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .client import RedisClient


class StreamService:
    """
    Redis Stream service.

    Provides stream production, consumer group
    management, message consumption, and
    acknowledgment for reliable event processing.
    """

    def __init__(
        self,
        client: RedisClient,
    ) -> None:

        self._client = client

    async def publish(
        self,
        stream: str,
        values: Dict[str, Any],
    ) -> str:
        """
        Publish message to stream.

        Args:
            stream: Stream name.
            values: Message fields and values.

        Returns:
            Message ID.
        """

        return await self._client.client.xadd(
            stream,
            values,
        )

    async def create_group(
        self,
        stream: str,
        group: str,
    ) -> None:
        """
        Create consumer group.

        Creates a new consumer group for a stream.
        Silently ignores if the group already exists.

        Args:
            stream: Stream name.
            group: Consumer group name.
        """

        try:
            await self._client.client.xgroup_create(
                stream,
                group,
                id="$",
                mkstream=True,
            )
        except Exception:
            pass

    async def read(
        self,
        group: str,
        consumer: str,
        stream: str,
        count: int = 10,
    ) -> List[Any]:
        """
        Read messages from stream via consumer group.

        Args:
            group: Consumer group name.
            consumer: Consumer name.
            stream: Stream name.
            count: Maximum number of messages to read.

        Returns:
            List of stream messages.
        """

        return await self._client.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
        )

    async def ack(
        self,
        stream: str,
        group: str,
        *ids: str,
    ) -> int:
        """
        Acknowledge processed messages.

        Args:
            stream: Stream name.
            group: Consumer group name.
            *ids: Message IDs to acknowledge.

        Returns:
            Number of messages acknowledged.
        """

        return await self._client.client.xack(
            stream,
            group,
            *ids,
        )

    async def delete(
        self,
        stream: str,
        group: str,
        *ids: str,
    ) -> int:
        """
        Delete messages from stream.

        Args:
            stream: Stream name.
            group: Consumer group name.
            *ids: Message IDs to delete.

        Returns:
            Number of messages deleted.
        """

        return await self._client.client.xdel(
            stream,
            *ids,
        )