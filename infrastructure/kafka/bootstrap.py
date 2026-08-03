"""
Kafka infrastructure bootstrap.

Provides lifecycle management and integration
with the application bootstrap system for
the complete Kafka event infrastructure.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .client import KafkaClient
from .consumer import KafkaConsumerService
from .envelope import EventEnvelope
from .eventbus import EventBus
from .health import KafkaHealth
from .metrics import (
    ConsumerMetrics,
    ProducerMetrics,
)
from .producer import KafkaProducerService
from .registry import TopicRegistry
from .router import EventRouter


class KafkaTracing:
    """
    OpenTelemetry tracing hooks for Kafka.

    Provides span creation for event publishing
    and consumption. This is a placeholder that
    will be extended with full OpenTelemetry
    integration in v0.5.x.
    """

    def __init__(
        self,
        service_name: str = "icyquant-kafka",
    ) -> None:

        self._service_name = service_name

    async def before_publish(
        self,
        event: EventEnvelope,
    ) -> Dict[str, Any]:
        """
        Create publish span.

        Args:
            event: Event envelope being published.

        Returns:
            Span context dictionary.
        """

        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "correlation_id": (
                event.correlation_id
            ),
            "service": self._service_name,
        }

    async def after_publish(
        self,
        event: EventEnvelope,
        success: bool = True,
    ) -> None:
        """
        Close publish span.

        Args:
            event: Event envelope that was published.
            success: Whether publishing succeeded.
        """

        pass

    async def before_consume(
        self,
        event: EventEnvelope,
    ) -> Dict[str, Any]:
        """
        Create consume span.

        Args:
            event: Event envelope being consumed.

        Returns:
            Span context dictionary.
        """

        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "correlation_id": (
                event.correlation_id
            ),
            "service": self._service_name,
        }

    async def after_consume(
        self,
        event: EventEnvelope,
        success: bool = True,
    ) -> None:
        """
        Close consume span.

        Args:
            event: Event envelope that was consumed.
            success: Whether processing succeeded.
        """

        pass


class KafkaBootstrap:
    """
    Kafka infrastructure bootstrap.

    Manages the complete Kafka infrastructure
    lifecycle including client initialization,
    service creation, event bus setup, and
    graceful shutdown.
    """

    def __init__(
        self,
        client: KafkaClient,
        topic_registry: Optional[TopicRegistry] = None,
    ) -> None:

        self.client = client

        self.producer = KafkaProducerService(
            client
        )

        self.consumer = KafkaConsumerService(
            client
        )

        self.registry = (
            topic_registry
            or TopicRegistry.with_defaults()
        )

        self.router = EventRouter(
            self.registry
        )

        self.eventbus = EventBus(
            self.producer,
            self.consumer,
            self.router,
        )

        self.health = KafkaHealth()

        self.tracing = KafkaTracing()

        self.producer_metrics = (
            ProducerMetrics()
        )

        self.consumer_metrics = (
            ConsumerMetrics()
        )

    async def startup(
        self,
    ) -> None:
        """
        Initialize Kafka infrastructure.

        Starts the Kafka producer connection
        and verifies connectivity.
        """

        await self.client.startup_producer()

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown Kafka infrastructure.

        Gracefully disconnects producer and
        consumer and releases all resources.
        """

        await self.client.shutdown_producer()

        await self.client.shutdown_consumer()

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Health status dictionary.
        """

        healthy, message = await self.health.check()

        return {
            "healthy": healthy,
            "message": message,
            "producer": {
                "published": (
                    self.producer_metrics.published_messages
                ),
                "failed": (
                    self.producer_metrics.failed_messages
                ),
            },
            "consumer": {
                "consumed": (
                    self.consumer_metrics.consumed_messages
                ),
                "failed": (
                    self.consumer_metrics.failed_messages
                ),
            },
            "topics": len(
                self.registry.list_topics()
            ),
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get infrastructure status.

        Returns:
            Status dictionary.
        """

        return {
            "initialized": (
                self.client.is_initialized
            ),
            "topics_registered": len(
                self.registry.list_events()
            ),
            "producer_metrics": (
                self.producer_metrics.snapshot()
            ),
            "consumer_metrics": (
                self.consumer_metrics.snapshot()
            ),
        }