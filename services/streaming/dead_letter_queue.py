"""
Dead Letter Queue — captures failed events for later inspection,
retry, or manual recovery, preventing data loss in stream processing.

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


class DLQStatus(str, Enum):
    PENDING = "pending"
    RETRYING = "retrying"
    REPLAYED = "replayed"
    FAILED = "failed"
    DISCARDED = "discarded"
    RESOLVED = "resolved"


@dataclass
class DLQEntry:
    """An entry in the dead letter queue."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    event: Any = None
    error: str = ""
    status: DLQStatus = DLQStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_retry_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DeadLetterQueue:
    """
    Captures failed events for inspection, retry, and recovery.

    Events that fail processing are moved to the DLQ instead of
    being silently dropped, enabling:
    - Manual inspection and replay
    - Automatic retry with backoff
    - Root cause analysis
    - Data loss prevention

    Flow:
        Failed Event → Retry → DLQ → Replay

    Usage::

        dlq = DeadLetterQueue()
        await dlq.send("market.tick", failed_event, "Deserialization error")
        entries = await dlq.list_pending()
        await dlq.replay(entry.entry_id, process_handler)
    """

    def __init__(self, max_entries: int = 100000) -> None:
        self.max_entries = max_entries
        self._entries: dict[str, DLQEntry] = {}
        self._topic_queues: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()

    async def send(
        self,
        topic: str,
        event: Any,
        error: str,
        *,
        max_retries: int = 3,
        metadata: Optional[dict[str, Any]] = None,
    ) -> DLQEntry:
        """Send a failed event to the DLQ."""
        async with self._lock:
            entry = DLQEntry(
                topic=topic,
                event=event,
                error=error,
                max_retries=max_retries,
                metadata=metadata or {},
            )

            self._entries[entry.entry_id] = entry

            if topic not in self._topic_queues:
                self._topic_queues[topic] = []
            self._topic_queues[topic].append(entry.entry_id)

            # Enforce max entries
            if len(self._entries) > self.max_entries:
                oldest = next(iter(self._entries.keys()))
                self._entries.pop(oldest, None)

            logger.warning(
                "DLQ: %s → %s: %s (entry=%s)",
                topic, error[:80], entry.entry_id[:8],
            )
            return entry

    async def get(self, entry_id: str) -> Optional[DLQEntry]:
        """Get a DLQ entry by ID."""
        return self._entries.get(entry_id)

    async def list_pending(self, topic: Optional[str] = None) -> list[DLQEntry]:
        """List pending DLQ entries."""
        entries = self._entries.values()
        if topic:
            entries = [e for e in entries if e.topic == topic]
        return [e for e in entries if e.status == DLQStatus.PENDING]

    async def list_all(self, topic: Optional[str] = None) -> list[DLQEntry]:
        """List all DLQ entries."""
        entries = list(self._entries.values())
        if topic:
            entries = [e for e in entries if e.topic == topic]
        return entries

    async def retry(
        self, entry_id: str, handler: Any
    ) -> bool:
        """Retry processing a DLQ entry."""
        entry = self._entries.get(entry_id)
        if entry is None:
            return False

        entry.status = DLQStatus.RETRYING
        entry.retry_count += 1
        entry.last_retry_at = datetime.now(timezone.utc)

        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(entry.event)
            elif callable(handler):
                handler(entry.event)
            entry.status = DLQStatus.REPLAYED
            entry.resolved_at = datetime.now(timezone.utc)
            return True
        except Exception as e:
            entry.error = str(e)
            if entry.retry_count >= entry.max_retries:
                entry.status = DLQStatus.FAILED
            else:
                entry.status = DLQStatus.PENDING
            return False

    async def replay(
        self, entry_id: str, handler: Any
    ) -> bool:
        """Alias for retry — replay a DLQ event."""
        return await self.retry(entry_id, handler)

    async def replay_all_pending(
        self, topic: str, handler: Any
    ) -> dict[str, bool]:
        """Replay all pending DLQ entries for a topic."""
        pending = await self.list_pending(topic)
        results = {}
        for entry in pending:
            results[entry.entry_id] = await self.retry(entry.entry_id, handler)
        return results

    async def discard(self, entry_id: str) -> bool:
        """Discard a DLQ entry."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.status = DLQStatus.DISCARDED
            entry.resolved_at = datetime.now(timezone.utc)
            return True
        return False

    async def clear(self, topic: Optional[str] = None) -> int:
        """Clear DLQ entries."""
        async with self._lock:
            if topic:
                entry_ids = self._topic_queues.pop(topic, [])
                for eid in entry_ids:
                    self._entries.pop(eid, None)
                return len(entry_ids)
            else:
                count = len(self._entries)
                self._entries.clear()
                self._topic_queues.clear()
                return count

    async def stats(self) -> dict[str, Any]:
        """Get DLQ statistics."""
        by_status: dict[str, int] = {}
        for e in self._entries.values():
            key = e.status.value
            by_status[key] = by_status.get(key, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_status": by_status,
            "by_topic": {
                topic: len(ids)
                for topic, ids in self._topic_queues.items()
            },
        }
