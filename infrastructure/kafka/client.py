"""
Kafka client.

Production-grade async Kafka client
with lazy import of aiokafka for optional
dependency support. Manages producer and
consumer lifecycle independently.
"""

from __future__ import annotations

from typing import Any, Optional

from .config import KafkaConfig
from .exceptions import (
    KafkaConnectionError,
)


class KafkaClient:
    """
    Kafka runtime client.

    Manages async Kafka producer and consumer
    connections with lazy initialization.
    Follows the same lazy-import pattern as
    RedisClient to avoid hard dependency failures.
    """

    def __init__(
        self,
        config: KafkaConfig,
    ) -> None:

        self._config = config

        self._producer: Optional[Any] = None

        self._consumer: Optional[Any] = None

    @property
    def config(
        self,
    ) -> KafkaConfig:
        """
        Return the Kafka configuration.
        """

        return self._config

    @property
    def is_initialized(
        self,
    ) -> bool:
        """
        Check if the client has been initialized.
        """

        return (
            self._producer is not None
            or self._consumer is not None
        )

    @property
    def producer(
        self,
    ):
        """
        Return the async Kafka producer.

        Raises KafkaConnectionError if the
        producer has not been started.
        """

        if self._producer is None:
            raise KafkaConnectionError(
                "Producer not started. "
                "Call startup_producer() first."
            )

        return self._producer

    @property
    def consumer(
        self,
    ):
        """
        Return the async Kafka consumer.

        Raises KafkaConnectionError if the
        consumer has not been started.
        """

        if self._consumer is None:
            raise KafkaConnectionError(
                "Consumer not started. "
                "Call startup_consumer() first."
            )

        return self._consumer

    def _get_aiokafka(
        self,
    ):
        """
        Lazy import aiokafka.

        Raises KafkaConnectionError if aiokafka
        is not installed.

        Returns:
            Tuple of (AIOKafkaProducer, AIOKafkaConsumer).
        """

        try:
            from aiokafka import (
                AIOKafkaConsumer,
                AIOKafkaProducer,
            )

            return (
                AIOKafkaProducer,
                AIOKafkaConsumer,
            )

        except ImportError:
            raise KafkaConnectionError(
                "aiokafka is not installed. "
                "Install with: pip install aiokafka"
            )

    async def startup_producer(
        self,
    ) -> None:
        """
        Initialize Kafka producer.

        Creates the AIOKafkaProducer with
        configured parameters and starts it.
        """

        AIOKafkaProducer, _ = self._get_aiokafka()

        self._producer = AIOKafkaProducer(
            bootstrap_servers=(
                self._config.bootstrap_servers
            ),
            client_id=(
                self._config.client_id
            ),
            compression_type=(
                self._config.compression_type
            ),
            enable_idempotence=(
                self._config.enable_idempotence
            ),
            linger_ms=(
                self._config.linger_ms
            ),
            acks=self._config.acks,
            retries=self._config.retries,
            retry_backoff_ms=(
                self._config.retry_backoff_ms
            ),
        )

        await self._producer.start()

    async def shutdown_producer(
        self,
    ) -> None:
        """
        Shutdown Kafka producer.

        Gracefully stops the producer and
        clears the reference.
        """

        if self._producer is not None:
            try:
                await self._producer.stop()
            except Exception:
                pass

            self._producer = None

    async def startup_consumer(
        self,
        *topics: str,
    ) -> None:
        """
        Initialize Kafka consumer.

        Creates the AIOKafkaConsumer with
        consumer group configuration and starts
        it with manual offset commit.

        Args:
            *topics: Kafka topics to subscribe to.
        """

        _, AIOKafkaConsumer = self._get_aiokafka()

        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=(
                self._config.bootstrap_servers
            ),
            group_id=self._config.group_id,
            client_id=(
                self._config.client_id
            ),
            enable_auto_commit=False,
            auto_offset_reset=(
                self._config.auto_offset_reset
            ),
            max_poll_interval_ms=(
                self._config.max_poll_interval_ms
            ),
            consumer_timeout_ms=(
                self._config.consumer_timeout_ms
            ),
        )

        await self._consumer.start()

    async def shutdown_consumer(
        self,
    ) -> None:
        """
        Shutdown Kafka consumer.

        Gracefully stops the consumer and
        clears the reference.
        """

        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                pass

            self._consumer = None
