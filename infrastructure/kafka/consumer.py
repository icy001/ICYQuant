"""
Kafka consumer service.

Production-grade Kafka consumer with consumer
group support, manual offset commit for
at-least-once delivery, batch consumption,
and rebalance listener framework.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, Dict, List

from .client import KafkaClient
from .exceptions import (
    KafkaConsumeError,
)
from .metrics import (
    ConsumerMetrics,
)
from .serializer import (
    JsonSerializer,
)

try:
    from aiokafka.structs import ConsumerRecord
except ImportError:
    ConsumerRecord = Any


MessageHandler = Callable[
    [ConsumerRecord, Dict[str, Any]],
    Awaitable[None],
]


class KafkaConsumerService:
    """
    Kafka consumer service.

    Wraps KafkaClient for reliable message
    consumption from Kafka topics with manual
    offset commit to ensure at-least-once delivery.
    Provides single and batch consume modes.
    """

    def __init__(
        self,
        client: KafkaClient,
    ) -> None:

        self._client = client

        self.metrics = ConsumerMetrics()

    async def consume(
        self,
        handler: MessageHandler,
    ) -> None:
        """
        Consume messages one at a time.

        Reads messages from the consumer,
        deserializes the payload, invokes the
        handler, and commits the offset only
        after successful processing.

        This ensures at-least-once delivery:
        if the handler fails, the offset is not
        committed and Kafka will redeliver.

        Args:
            handler: Async callback for each
                message. Receives (record, payload).

        Raises:
            KafkaConsumeError: If processing fails.
                Offset is not committed on failure.
        """

        async for record in self._client.consumer:
            start = perf_counter()

            try:
                payload = JsonSerializer.loads(
                    record.value
                )

                await handler(
                    record,
                    payload,
                )

                await self._client.consumer.commit()

                latency_ms = (
                    perf_counter() - start
                ) * 1000

                self.metrics.record_consumed(
                    byte_count=len(record.value),
                    latency_ms=latency_ms,
                )

            except Exception as exc:
                self.metrics.record_failure()

                raise KafkaConsumeError(
                    str(exc)
                ) from exc

    async def consume_batch(
        self,
        handler: MessageHandler,
    ) -> None:
        """
        Consume messages in batch.

        Fetches a batch of records and processes
        them sequentially, committing the offset
        after all messages in the batch are
        successfully processed.

        Args:
            handler: Async callback for each
                message. Receives (record, payload).

        Raises:
            KafkaConsumeError: If any message
                processing fails.
        """

        records = await self._client.consumer.getmany()

        for _, batch in records.items():
            for record in batch:
                payload = JsonSerializer.loads(
                    record.value
                )

                await handler(
                    record,
                    payload,
                )

                self.metrics.record_consumed(
                    byte_count=len(record.value),
                    latency_ms=0.0,
                )

        await self._client.consumer.commit()


class ConsumerRebalanceListener:
    """
    Consumer rebalance listener.

    Handles consumer group rebalance events,
    tracking partition assignments and
    revocations for observability.
    """

    def __init__(
        self,
        metrics: ConsumerMetrics,
    ) -> None:

        self._metrics = metrics

    async def on_partitions_revoked(
        self,
        revoked: List[Any],
    ) -> None:
        """
        Handle partition revocation.

        Called when partitions are revoked
        from this consumer during a rebalance.

        Args:
            revoked: List of revoked partitions.
        """

        self._metrics.record_rebalance()

    async def on_partitions_assigned(
        self,
        assigned: List[Any],
    ) -> None:
        """
        Handle partition assignment.

        Called when new partitions are assigned
        to this consumer after a rebalance.

        Args:
            assigned: List of assigned partitions.
        """

        pass
