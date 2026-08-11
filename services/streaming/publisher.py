"""
Publisher — event publishing with batching, acknowledgment, and
partition-aware routing.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PublishStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    QUEUED = "queued"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class PublishResult:
    """Result of a publish operation."""
    event_id: str
    topic: str
    partition: int = 0
    offset: int = 0
    success: bool = True
    status: PublishStatus = PublishStatus.SUCCESS
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str = ""
    latency_ms: float = 0.0


@dataclass
class PublishAck:
    """Acknowledgment from the streaming platform for a published event."""
    event_id: str
    topic: str
    partition: int
    offset: int
    committed: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Publisher:
    """
    Event publisher with batching and partition-aware routing.

    Features:
    - Synchronous and async publish
    - Batch publishing with configurable size
    - Partition key-based routing
    - Publish acknowledgment tracking
    - Latency measurement

    Usage::

        publisher = Publisher(metrics, telemetry)
        result = await publisher.publish("market.tick", {"symbol": "BTC", "price": 50000})
        results = await publisher.publish_batch("market.tick", events)
    """

    def __init__(self, metrics: Any = None, telemetry: Any = None) -> None:
        self.metrics = metrics
        self.telemetry = telemetry
        self._pending_acks: dict[str, PublishAck] = {}
        self._batch_buffers: dict[str, list[Any]] = {}
        self._batch_locks: dict[str, asyncio.Lock] = {}
        self._total_published = 0
        self._total_errors = 0

    async def publish(
        self,
        topic: str,
        payload: Any,
        *,
        key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        partition: Optional[int] = None,
        timeout_ms: int = 5000,
    ) -> PublishResult:
        """Publish a single event to a topic."""
        event_id = str(uuid.uuid4())
        start = time.monotonic()

        try:
            # In production, this would serialize and send to the broker
            # Here we simulate the publish path
            result = PublishResult(
                event_id=event_id,
                topic=topic,
                partition=partition or (hash(key) % 8 if key else 0),
                offset=self._total_published,
                success=True,
                status=PublishStatus.SUCCESS,
                latency_ms=(time.monotonic() - start) * 1000,
            )

            self._total_published += 1
            self._pending_acks[event_id] = PublishAck(
                event_id=event_id,
                topic=topic,
                partition=result.partition,
                offset=result.offset,
            )

            if self.metrics:
                self.metrics.record_publish(topic, True)

            logger.debug(
                "Published: %s → %s[%d] offset=%d (%.2fms)",
                event_id[:8], topic, result.partition, result.offset, result.latency_ms,
            )
            return result

        except Exception as e:
            self._total_errors += 1
            if self.metrics:
                self.metrics.record_publish(topic, False)

            return PublishResult(
                event_id=event_id,
                topic=topic,
                success=False,
                status=PublishStatus.FAILED,
                error=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    async def publish_batch(
        self,
        topic: str,
        events: list[Any],
        *,
        keys: Optional[list[str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_ms: int = 30000,
    ) -> list[PublishResult]:
        """Publish a batch of events."""
        results = []
        for i, event in enumerate(events):
            key = keys[i] if keys and i < len(keys) else None
            result = await self.publish(
                topic=topic,
                payload=event,
                key=key,
                headers=headers,
                timeout_ms=timeout_ms,
            )
            results.append(result)

        logger.info("Published batch: %d events → %s", len(results), topic)
        return results

    async def flush(self, topic: Optional[str] = None) -> int:
        """Flush any pending publish buffers."""
        if topic:
            flushed = len(self._batch_buffers.pop(topic, []))
        else:
            flushed = sum(len(b) for b in self._batch_buffers.values())
            self._batch_buffers.clear()
        return flushed

    async def get_ack(self, event_id: str) -> Optional[PublishAck]:
        """Get acknowledgment for a published event."""
        return self._pending_acks.get(event_id)

    async def wait_for_ack(self, event_id: str, timeout_ms: int = 5000) -> Optional[PublishAck]:
        """Wait for acknowledgment of a published event."""
        start = time.monotonic()
        while (time.monotonic() - start) * 1000 < timeout_ms:
            ack = self._pending_acks.get(event_id)
            if ack:
                return ack
            await asyncio.sleep(0.001)
        return None

    @property
    def total_published(self) -> int:
        return self._total_published

    @property
    def total_errors(self) -> int:
        return self._total_errors

    async def stats(self) -> dict[str, Any]:
        """Get publisher statistics."""
        return {
            "total_published": self._total_published,
            "total_errors": self._total_errors,
            "pending_acks": len(self._pending_acks),
            "error_rate": (
                self._total_errors / max(self._total_published, 1)
            ),
        }
