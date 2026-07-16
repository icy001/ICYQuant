"""
Simple event publisher.

Future implementation:

Kafka

RabbitMQ

Redis Streams
"""

from __future__ import annotations

from typing import Callable


class EventPublisher:

    def __init__(self):

        self._handlers: list[
            Callable
        ] = []

    def subscribe(

        self,

        handler: Callable,

    ) -> None:

        self._handlers.append(
            handler
        )

    async def publish(

        self,

        event,

    ) -> None:

        for handler in self._handlers:

            result = handler(event)

            if hasattr(
                result,
                "__await__",
            ):
                await result