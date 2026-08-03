"""
Event Bus.

Central event bus for ICYQuant providing
a unified interface for event publishing
and subscribing. All business modules should
use EventBus instead of direct Kafka API.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, Optional

from .consumer import (
    KafkaConsumerService,
)
from .envelope import (
    EventEnvelope,
)
from .producer import (
    KafkaProducerService,
)
from .router import EventRouter
from .retry import RetryPolicy
from .deadletter import DeadLetterMessage


EventHandler = Callable[
    [EventEnvelope],
    Awaitable[None],
]


class EventBus:
    """
    Production event bus.

    Provides a unified interface for publishing
    and subscribing to events across the ICYQuant
    platform. All business modules interact with
    the EventBus, not directly with Kafka.

    Features:
    - Event envelope creation and serialization
    - Topic resolution via EventRouter
    - Manual offset commit for at-least-once delivery
    - Retry policy with dead letter queue
    - Correlation ID propagation
    """

    def __init__(
        self,
        producer: KafkaProducerService,
        consumer: KafkaConsumerService,
        router: EventRouter,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:

        self._producer = producer
        self._consumer = consumer
        self._router = router
        self._retry_policy = (
            retry_policy or RetryPolicy()
        )

        self._subscriptions: Dict[
            str, List[EventHandler]
        ] = {}

    async def publish(
        self,
        event: EventEnvelope,
    ) -> None:
        """
        Publish an event to its Kafka topic.

        Resolves the event type to a topic via
        the EventRouter, serializes the envelope,
        and sends it via the Kafka producer.

        Args:
            event: Event envelope to publish.

        Raises:
            KeyError: If event type is not registered.
            KafkaPublishError: If publishing fails.
        """

        topic = self._router.topic(
            event.event_type
        )

        await self._producer.publish(
            topic,
            event.to_dict(),
        )

    async def publish_with_key(
        self,
        event: EventEnvelope,
        key: str,
    ) -> None:
        """
        Publish an event with a routing key.

        Ensures ordered processing for events
        sharing the same key (e.g., same order ID).

        Args:
            event: Event envelope to publish.
            key: Routing key for partition assignment.
        """

        topic = self._router.topic(
            event.event_type
        )

        await self._producer.publish_with_key(
            topic,
            key,
            event.to_dict(),
        )

    async def publish_batch(
        self,
        events: List[EventEnvelope],
    ) -> None:
        """
        Publish multiple events in batch.

        Args:
            events: List of event envelopes.
        """

        for event in events:
            topic = self._router.topic(
                event.event_type
            )
            await self._producer.publish(
                topic,
                event.to_dict(),
            )

    async def subscribe(
        self,
        handler: EventHandler,
        event_type: Optional[str] = None,
    ) -> None:
        """
        Subscribe to events and dispatch to handler.

        Wraps the Kafka consumer to deserialize
        EventEnvelope objects and invoke the handler.
        Supports optional event type filtering.

        Args:
            handler: Async callback for each event.
            event_type: Optional event type filter.
                If set, only events of this type
                are passed to the handler.
        """

        async def wrapper(
            record: Any,
            payload: Dict[str, Any],
        ) -> None:
            envelope = EventEnvelope.from_dict(
                payload
            )

            if event_type and (
                envelope.event_type
                != event_type
            ):
                return

            await handler(envelope)

        await self._consumer.consume(wrapper)

    async def subscribe_batch(
        self,
        handler: EventHandler,
    ) -> None:
        """
        Subscribe to events in batch mode.

        Args:
            handler: Async callback for each event.
        """

        async def wrapper(
            record: Any,
            payload: Dict[str, Any],
        ) -> None:
            envelope = EventEnvelope.from_dict(
                payload
            )
            await handler(envelope)

        await self._consumer.consume_batch(
            wrapper
        )

    async def handle_failure(
        self,
        event: EventEnvelope,
        error: Exception,
        retry_count: int,
    ) -> None:
        """
        Handle event processing failure.

        Routes failed events to retry topics
        or dead letter queue based on retry policy.

        Args:
            event: Failed event envelope.
            error: Exception that caused failure.
            retry_count: Number of retries attempted.
        """

        if self._retry_policy.is_exhausted(
            retry_count
        ):
            # Send to dead letter queue
            dlq_topic = (
                self._router.dead_letter_topic(
                    event.event_type
                )
            )

            dlq_msg = DeadLetterMessage.create(
                topic=self._router.topic(
                    event.event_type
                ),
                reason=str(error),
                payload=event.to_dict()
                .__repr__()
                .encode(),
                retry_count=retry_count,
                original_event_id=event.event_id,
            )

            await self._producer.publish(
                dlq_topic,
                dlq_msg.to_dict(),
            )

        else:
            # Send to retry topic
            retry_topic = self._router.retry_topic(
                event.event_type
            )

            retry_envelope = EventEnvelope.create(
                event_type=event.event_type,
                payload={
                    "original_payload": (
                        event.payload
                    ),
                    "retry_count": (
                        retry_count + 1
                    ),
                    "error": str(error),
                    "original_event_id": (
                        event.event_id
                    ),
                },
                source=f"{event.source}.retry",
                correlation_id=(
                    event.correlation_id
                ),
            )

            await self._producer.publish(
                retry_topic,
                retry_envelope.to_dict(),
            )
