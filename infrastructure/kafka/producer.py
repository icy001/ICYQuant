"""
Kafka producer service.

Production-grade Kafka producer with
batch publishing, key-based routing,
automatic serialization, and metrics
tracking for the ICYQuant event bus.
"""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, List

from .client import KafkaClient
from .exceptions import (
    KafkaPublishError,
)
from .metrics import (
    ProducerMetrics,
)
from .serializer import (
    JsonSerializer,
)


class KafkaProducerService:
    """
    Kafka producer service.

    Wraps KafkaClient for reliable message
    publishing to Kafka topics. Provides
    serialization, batch operations,
    key-based routing, and metrics tracking.
    """

    def __init__(
        self,
        client: KafkaClient,
    ) -> None:

        self._client = client

        self.metrics = ProducerMetrics()

    async def publish(
        self,
        topic: str,
        message: Any,
    ) -> None:
        """
        Publish a single message to a topic.

        Serializes the message to JSON and sends
        it to the specified Kafka topic with
        automatic metrics tracking.

        Args:
            topic: Kafka topic name.
            message: Message payload (any
                JSON-serializable object).

        Raises:
            KafkaPublishError: If publishing fails.
        """

        payload = JsonSerializer.dumps(
            message
        )

        start = perf_counter()

        try:
            await self._client.producer.send_and_wait(
                topic,
                payload,
            )

            latency_ms = (
                perf_counter() - start
            ) * 1000

            self.metrics.record_success(
                byte_count=len(payload),
                latency_ms=latency_ms,
            )

        except Exception as exc:
            self.metrics.record_failure()

            raise KafkaPublishError(
                str(exc)
            ) from exc

    async def publish_batch(
        self,
        topic: str,
        messages: List[Any],
    ) -> None:
        """
        Publish multiple messages to a topic.

        Sends messages concurrently using
        asyncio.gather for maximum throughput.

        Args:
            topic: Kafka topic name.
            messages: List of message payloads.

        Raises:
            KafkaPublishError: If any message
                fails to publish.
        """

        tasks = [
            self.publish(
                topic,
                msg,
            )
            for msg in messages
        ]

        await asyncio.gather(*tasks)

    async def publish_with_key(
        self,
        topic: str,
        key: str,
        message: Any,
    ) -> None:
        """
        Publish a message with a routing key.

        Key-based publishing ensures that
        messages with the same key are routed
        to the same partition, preserving order.

        Args:
            topic: Kafka topic name.
            key: Routing key for partition
                assignment.
            message: Message payload.

        Raises:
            KafkaPublishError: If publishing fails.
        """

        payload = JsonSerializer.dumps(
            message
        )

        start = perf_counter()

        try:
            await self._client.producer.send_and_wait(
                topic,
                payload,
                key=key.encode(),
            )

            latency_ms = (
                perf_counter() - start
            ) * 1000

            self.metrics.record_success(
                byte_count=len(payload),
                latency_ms=latency_ms,
            )

        except Exception as exc:
            self.metrics.record_failure()

            raise KafkaPublishError(
                str(exc)
            ) from exc
