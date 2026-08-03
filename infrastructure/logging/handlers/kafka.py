"""
Kafka log handler.

Sends log records to Kafka topics,
enabling centralized log aggregation
across multiple services.

Supports multiple topics for different
log categories:
- logs.application: General application logs
- logs.audit: Audit trail logs
- logs.trade: Trade execution logs
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..exceptions import HandlerError
from ..models import LogEntry
from .base import LogHandler


class KafkaLogHandler(LogHandler):
    """
    Kafka log handler.

    Publishes log records to Kafka topics
    for centralized log aggregation.

    Features:
    - Topic routing by log category
    - Async producer integration
    - Graceful degradation when unavailable
    - Configurable topic mapping

    Usage:
        handler = KafkaLogHandler(
            producer=my_kafka_producer,
            default_topic="logs.application",
        )
        await handler.startup()
        await handler.emit(log_entry)
        await handler.shutdown()
    """

    def __init__(
        self,
        producer: Any = None,
        default_topic: str = "logs.application",
        topic_mapping: Optional[dict] = None,
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize Kafka log handler.

        Args:
            producer: Kafka async producer instance.
            default_topic: Default topic for logs.
            topic_mapping: Maps logger names to topics.
            name: Optional handler name.
        """

        super().__init__(name=name)
        self._producer = producer
        self._default_topic = default_topic
        self._topic_mapping = topic_mapping or {
            "audit": "logs.audit",
            "trade": "logs.trade",
            "risk": "logs.risk",
        }

    async def startup(
        self,
    ) -> None:
        """Start the handler."""

        self._started = True

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Publish a log record to Kafka.

        Args:
            record: LogEntry to publish.
        """

        try:
            if self._producer is None:
                self._emit_count += 1
                return

            topic = self._resolve_topic(record)
            payload = record.to_json().encode("utf-8")

            # Send to Kafka (async)
            await self._producer.send_and_wait(
                topic=topic,
                value=payload,
                key=record.trace_id.encode("utf-8")
                if record.trace_id
                else None,
            )

            self._emit_count += 1
        except Exception:
            self._error_count += 1

    async def shutdown(
        self,
    ) -> None:
        """Shutdown the handler."""

        self._started = False

    def _resolve_topic(
        self,
        record: LogEntry,
    ) -> str:
        """
        Resolve the Kafka topic for a log record.

        Args:
            record: LogEntry to resolve.

        Returns:
            Kafka topic name.
        """

        for keyword, topic in self._topic_mapping.items():
            if keyword in record.logger.lower():
                return topic

        return self._default_topic

    def get_status(
        self,
    ) -> dict:
        """Get handler status."""

        status = super().get_status()
        status["default_topic"] = self._default_topic
        status["producer"] = (
            type(self._producer).__name__
            if self._producer
            else None
        )
        return status
