"""
Stream Manager — lifecycle management for individual event streams,
monitoring stream health, throughput, and lag.

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


class StreamStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    BACKPRESSURE = "backpressure"
    DRAINING = "draining"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class StreamInfo:
    """Metadata and statistics for a managed stream."""
    stream_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    status: StreamStatus = StreamStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events_published: int = 0
    events_consumed: int = 0
    bytes_published: int = 0
    bytes_consumed: int = 0
    current_lag: int = 0
    subscribers: int = 0
    last_event_at: Optional[datetime] = None
    avg_throughput_per_sec: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamManager:
    """
    Lifecycle manager for individual event streams.

    Tracks each stream's health, throughput, subscriber count,
    and consumer lag. Provides pause/resume/drain controls.

    Usage::

        mgr = StreamManager()
        stream = await mgr.create("market.tick")
        await mgr.update_stats("market.tick", events_published=100)
        await mgr.pause("market.tick")
    """

    def __init__(self) -> None:
        self._streams: dict[str, StreamInfo] = {}
        self._lock = asyncio.Lock()

    async def create(self, topic: str, metadata: Optional[dict[str, Any]] = None) -> StreamInfo:
        """Create a managed stream for a topic."""
        async with self._lock:
            if topic in self._streams:
                return self._streams[topic]

            stream = StreamInfo(
                topic=topic,
                status=StreamStatus.CREATED,
                metadata=metadata or {},
            )
            self._streams[topic] = stream
            logger.info("Stream created: %s", topic)
            return stream

    async def activate(self, topic: str) -> bool:
        """Activate a stream (start accepting events)."""
        stream = self._streams.get(topic)
        if stream and stream.status in (StreamStatus.CREATED, StreamStatus.INACTIVE, StreamStatus.PAUSED):
            stream.status = StreamStatus.ACTIVE
            return True
        return False

    async def pause(self, topic: str) -> bool:
        """Pause a stream (stop accepting events)."""
        stream = self._streams.get(topic)
        if stream and stream.status == StreamStatus.ACTIVE:
            stream.status = StreamStatus.PAUSED
            return True
        return False

    async def resume(self, topic: str) -> bool:
        """Resume a paused stream."""
        stream = self._streams.get(topic)
        if stream and stream.status == StreamStatus.PAUSED:
            stream.status = StreamStatus.ACTIVE
            return True
        return False

    async def drain(self, topic: str) -> bool:
        """Drain a stream (process remaining, then close)."""
        stream = self._streams.get(topic)
        if stream:
            stream.status = StreamStatus.DRAINING
            return True
        return False

    async def close(self, topic: str) -> bool:
        """Close a stream permanently."""
        stream = self._streams.get(topic)
        if stream:
            stream.status = StreamStatus.CLOSED
            logger.info("Stream closed: %s", topic)
            return True
        return False

    async def delete(self, topic: str) -> bool:
        """Delete a stream."""
        async with self._lock:
            if topic in self._streams:
                del self._streams[topic]
                return True
        return False

    async def update_stats(
        self,
        topic: str,
        *,
        events_published: int = 0,
        events_consumed: int = 0,
        bytes_published: int = 0,
        bytes_consumed: int = 0,
        subscribers: Optional[int] = None,
    ) -> None:
        """Update stream statistics."""
        stream = self._streams.get(topic)
        if stream is None:
            return

        stream.events_published += events_published
        stream.events_consumed += events_consumed
        stream.bytes_published += bytes_published
        stream.bytes_consumed += bytes_consumed
        stream.current_lag = max(0, stream.events_published - stream.events_consumed)

        if subscribers is not None:
            stream.subscribers = subscribers

        if events_published > 0 or events_consumed > 0:
            stream.last_event_at = datetime.now(timezone.utc)

    async def update_throughput(self, topic: str, throughput: float) -> None:
        """Update average throughput (events/sec)."""
        stream = self._streams.get(topic)
        if stream:
            stream.avg_throughput_per_sec = throughput

    async def get(self, topic: str) -> Optional[StreamInfo]:
        """Get stream info by topic."""
        return self._streams.get(topic)

    async def list_all(self) -> list[StreamInfo]:
        """List all managed streams."""
        return list(self._streams.values())

    async def list_active(self) -> list[StreamInfo]:
        """List active streams."""
        return [s for s in self._streams.values() if s.status == StreamStatus.ACTIVE]

    async def count(self) -> int:
        """Count managed streams."""
        return len(self._streams)

    async def count_by_status(self) -> dict[str, int]:
        """Count streams grouped by status."""
        counts: dict[str, int] = {}
        for s in self._streams.values():
            key = s.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def total_lag(self) -> int:
        """Get total consumer lag across all streams."""
        return sum(s.current_lag for s in self._streams.values())

    async def summary(self) -> dict[str, Any]:
        """Get a summary of all managed streams."""
        return {
            "total_streams": len(self._streams),
            "by_status": await self.count_by_status(),
            "total_lag": await self.total_lag(),
            "total_published": sum(s.events_published for s in self._streams.values()),
            "total_consumed": sum(s.events_consumed for s in self._streams.values()),
            "total_subscribers": sum(s.subscribers for s in self._streams.values()),
        }
