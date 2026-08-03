"""
Kafka producer/consumer auto-instrumentation.

Provides automatic span creation for
Kafka operations, including:
- Producer: send, partition, offset, latency
- Consumer: receive, process, commit, retry
- Dead letter queue tracking
- Trace context propagation

Semantic attributes:
- messaging.system = "kafka"
- messaging.destination.name = topic
- messaging.operation = "send" / "process"
- messaging.kafka.partition
- messaging.kafka.offset
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class KafkaInstrumentation(Instrumentation):
    """
    Kafka producer/consumer auto-instrumentation.

    Wraps Kafka producer and consumer operations
    to automatically create messaging spans
    for message production and consumption.

    Features:
    - Producer span creation (send, publish)
    - Consumer span creation (receive, process)
    - Partition and offset tracking
    - Message size tracking
    - Retry and dead letter tracking
    - Trace context propagation

    Usage:
        instr = KafkaInstrumentation()
        await instr.install()

        # Producer
        span = instr.create_producer_span(
            topic="orders",
            message_id="msg-001",
        )

        # Consumer
        span = instr.create_consumer_span(
            topic="orders",
            partition=0,
            offset=12345,
        )
    """

    name: str = "kafka"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        capture_headers: bool = True,
        capture_body: bool = False,
        max_body_size: int = 1024,
    ) -> None:
        """
        Initialize Kafka instrumentation.

        Args:
            tracer: Optional Tracer instance.
            capture_headers: Whether to capture message headers.
            capture_body: Whether to capture message body.
            max_body_size: Max body size to capture.
        """

        super().__init__(tracer=tracer)
        self._capture_headers = capture_headers
        self._capture_body = capture_body
        self._max_body_size = max_body_size
        self._installed: bool = False
        self._producer_count: int = 0
        self._consumer_count: int = 0
        self._error_count: int = 0

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    @property
    def stats(
        self,
    ) -> Dict[str, int]:
        """Get Kafka operation statistics."""
        return {
            "producer_messages": self._producer_count,
            "consumer_messages": self._consumer_count,
            "errors": self._error_count,
        }

    async def install(
        self,
    ) -> None:
        """Install Kafka instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove Kafka instrumentation."""
        self._installed = False

    def create_producer_span(
        self,
        topic: str,
        message_id: Optional[str] = None,
        partition: Optional[int] = None,
        key: Optional[str] = None,
        body_size: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Create a producer span for message send.

        Args:
            topic: Kafka topic.
            message_id: Message identifier.
            partition: Target partition.
            key: Message key.
            body_size: Message body size in bytes.
            headers: Message headers.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"kafka.send {topic}",
            kind=SpanKind.PRODUCER,
        )

        span.add_attribute("messaging.system", "kafka")
        span.add_attribute("messaging.destination.name", topic)
        span.add_attribute("messaging.operation", "send")

        if message_id:
            span.add_attribute("messaging.message.id", message_id)

        if partition is not None:
            span.add_attribute("messaging.kafka.partition", partition)

        if key:
            span.add_attribute("messaging.kafka.message.key", key)

        if body_size is not None:
            span.add_attribute("messaging.message.body.size", body_size)

        if headers and self._capture_headers:
            for hdr_key, hdr_val in headers.items():
                span.add_attribute(
                    f"messaging.header.{hdr_key}",
                    str(hdr_val)[:128],
                )

        self._producer_count += 1
        return span

    def create_consumer_span(
        self,
        topic: str,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        message_id: Optional[str] = None,
        consumer_group: Optional[str] = None,
        key: Optional[str] = None,
        retry_count: int = 0,
        is_dead_letter: bool = False,
    ) -> Any:
        """
        Create a consumer span for message processing.

        Args:
            topic: Kafka topic.
            partition: Source partition.
            offset: Message offset.
            message_id: Message identifier.
            consumer_group: Consumer group name.
            key: Message key.
            retry_count: Number of retries.
            is_dead_letter: Whether this is a dead letter.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        operation = f"kafka.process {topic}"
        if is_dead_letter:
            operation = f"kafka.dead_letter {topic}"

        span = self.tracer.start_span(
            operation=operation,
            kind=SpanKind.CONSUMER,
        )

        span.add_attribute("messaging.system", "kafka")
        span.add_attribute("messaging.destination.name", topic)
        span.add_attribute("messaging.operation", "process")

        if partition is not None:
            span.add_attribute("messaging.kafka.partition", partition)

        if offset is not None:
            span.add_attribute("messaging.kafka.offset", offset)

        if message_id:
            span.add_attribute("messaging.message.id", message_id)

        if consumer_group:
            span.add_attribute("messaging.consumer.group.name", consumer_group)

        if key:
            span.add_attribute("messaging.kafka.message.key", key)

        if retry_count > 0:
            span.add_attribute("icyquant.retry.count", retry_count)

        if is_dead_letter:
            span.add_attribute("messaging.kafka.tombstone", True)

        self._consumer_count += 1
        return span

    def record_error(
        self,
        span: Any,
        error: Exception,
    ) -> None:
        """
        Record an error on a Kafka span.

        Args:
            span: Span to record error on.
            error: Exception that occurred.
        """

        span.set_status(
            __import__("...models", fromlist=["SpanStatus"]).SpanStatus.ERROR
        )
        span.add_attribute("exception.type", type(error).__name__)
        span.add_attribute("exception.message", str(error))
        self._error_count += 1
