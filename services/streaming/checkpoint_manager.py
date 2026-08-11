"""
Checkpoint Manager — fault-tolerance through periodic state
checkpointing for recoverable stream processing.

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


class CheckpointMode(str, Enum):
    EXACTLY_ONCE = "exactly_once"
    AT_LEAST_ONCE = "at_least_once"


@dataclass
class CheckpointRecord:
    """A checkpoint record."""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    offset: int = 0
    state_snapshot: Optional[dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """
    Manages checkpoints for fault-tolerant stream processing.

    Periodically snapshots stream offsets and state for recovery
    after failures.

    Flow:
        Process → Checkpoint → Commit

    Usage::

        mgr = CheckpointManager(checkpoint_interval_ms=10000)
        await mgr.initialize()
        ckpt = await mgr.create_checkpoint("market.tick", offset=1000, state=snapshot)
        restored = await mgr.restore("market.tick", ckpt.checkpoint_id)
    """

    def __init__(
        self,
        checkpoint_interval_ms: int = 10000,
        max_checkpoints_per_topic: int = 100,
        mode: CheckpointMode = CheckpointMode.EXACTLY_ONCE,
    ) -> None:
        self.checkpoint_interval_ms = checkpoint_interval_ms
        self.max_checkpoints_per_topic = max_checkpoints_per_topic
        self.mode = mode
        self._checkpoints: dict[str, list[CheckpointRecord]] = {}
        self._latest_checkpoints: dict[str, CheckpointRecord] = {}
        self._lock = asyncio.Lock()
        self._auto_checkpoint_task: Optional[asyncio.Task[None]] = None

    async def initialize(self) -> None:
        """Initialize the checkpoint manager."""
        logger.info("CheckpointManager initialized (mode=%s, interval=%dms)",
                    self.mode.value, self.checkpoint_interval_ms)

    async def stop(self) -> None:
        """Stop the checkpoint manager."""
        if self._auto_checkpoint_task:
            self._auto_checkpoint_task.cancel()
        logger.info("CheckpointManager stopped.")

    async def create_checkpoint(
        self,
        topic: str,
        *,
        offset: int = 0,
        state: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CheckpointRecord:
        """Create a checkpoint for a topic."""
        async with self._lock:
            record = CheckpointRecord(
                topic=topic,
                offset=offset,
                state_snapshot=state,
                metadata=metadata or {},
            )

            if topic not in self._checkpoints:
                self._checkpoints[topic] = []

            self._checkpoints[topic].append(record)
            self._latest_checkpoints[topic] = record

            # Enforce max checkpoints
            while len(self._checkpoints[topic]) > self.max_checkpoints_per_topic:
                removed = self._checkpoints[topic].pop(0)
                logger.debug("Evicted old checkpoint: %s", removed.checkpoint_id[:8])

            logger.debug(
                "Checkpoint created: %s/%s (offset=%d)",
                topic, record.checkpoint_id[:8], offset,
            )
            return record

    async def get_latest(self, topic: str) -> Optional[CheckpointRecord]:
        """Get the latest checkpoint for a topic."""
        return self._latest_checkpoints.get(topic)

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointRecord]:
        """Get a specific checkpoint by ID."""
        for records in self._checkpoints.values():
            for r in records:
                if r.checkpoint_id == checkpoint_id:
                    return r
        return None

    async def restore(self, topic: str, checkpoint_id: str) -> bool:
        """Restore state from a checkpoint."""
        record = await self.get_checkpoint(checkpoint_id)
        if record is None or record.topic != topic:
            return False
        logger.info("Restored checkpoint %s for topic %s", checkpoint_id[:8], topic)
        return True

    async def list_checkpoints(self, topic: str) -> list[CheckpointRecord]:
        """List all checkpoints for a topic."""
        return self._checkpoints.get(topic, [])

    async def delete_checkpoints(self, topic: str) -> int:
        """Delete all checkpoints for a topic."""
        async with self._lock:
            count = len(self._checkpoints.get(topic, []))
            self._checkpoints.pop(topic, None)
            self._latest_checkpoints.pop(topic, None)
            return count

    async def summary(self) -> dict[str, Any]:
        """Get checkpoint manager summary."""
        total = sum(len(v) for v in self._checkpoints.values())
        return {
            "mode": self.mode.value,
            "interval_ms": self.checkpoint_interval_ms,
            "total_checkpoints": total,
            "topics": {
                topic: {
                    "count": len(records),
                    "latest_offset": records[-1].offset if records else 0,
                }
                for topic, records in self._checkpoints.items()
            },
        }
