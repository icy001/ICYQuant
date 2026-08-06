"""Shard Manager — distributes workflow instances across shards.

Partitioning strategies:

* **Hash** — consistent hash by workflow_id for even distribution
* **Range** — key-range based partitioning
* **Dynamic** — adaptive sharding based on load

Shard → Worker mapping is maintained for intelligent dispatch.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ShardStrategy(str, Enum):
    """Partitioning strategies for workflow sharding."""

    HASH = "hash"
    RANGE = "range"
    DYNAMIC = "dynamic"


@dataclass
class Shard:
    """A single shard in the workflow cluster."""

    shard_id: str
    strategy: ShardStrategy = ShardStrategy.HASH
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    worker_node_id: Optional[str] = None
    workflow_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "strategy": self.strategy.value,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "worker_node_id": self.worker_node_id,
            "workflow_count": self.workflow_count,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


class ShardManager:
    """Manages workflow sharding across the cluster.

    Usage::

        mgr = ShardManager(shard_count=16, strategy=ShardStrategy.HASH)
        await mgr.start()
        shard_id = await mgr.assign_shard("workflow_abc")
    """

    def __init__(
        self,
        *,
        shard_count: int = 16,
        strategy: ShardStrategy = ShardStrategy.HASH,
    ) -> None:
        self._shard_count = shard_count
        self._strategy = strategy
        self._lock = threading.RLock()
        self._shards: Dict[str, Shard] = {}
        self._workflow_assignments: Dict[str, str] = {}  # workflow_id → shard_id
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        # Initialise shards
        with self._lock:
            for i in range(self._shard_count):
                shard_id = f"shard-{i:04d}"
                self._shards[shard_id] = Shard(
                    shard_id=shard_id,
                    strategy=self._strategy,
                )
        logger.info("ShardManager: started with %d shards (strategy=%s)",
                     self._shard_count, self._strategy.value)

    async def stop(self) -> None:
        self._started = False
        with self._lock:
            self._shards.clear()
            self._workflow_assignments.clear()
        logger.info("ShardManager: stopped")

    # ------------------------------------------------------------------
    # Shard assignment
    # ------------------------------------------------------------------

    async def assign_shard(self, workflow_id: str) -> str:
        """Assign a workflow to a shard and return the shard_id."""
        with self._lock:
            # Check existing assignment
            if workflow_id in self._workflow_assignments:
                return self._workflow_assignments[workflow_id]

            # Compute shard
            if self._strategy == ShardStrategy.HASH:
                shard_id = self._hash_shard(workflow_id)
            elif self._strategy == ShardStrategy.RANGE:
                shard_id = self._range_shard(workflow_id)
            else:
                shard_id = self._dynamic_shard()

            self._workflow_assignments[workflow_id] = shard_id
            shard = self._shards[shard_id]
            shard.workflow_count += 1

        logger.debug("ShardManager: workflow %s → %s", workflow_id, shard_id)
        return shard_id

    async def get_shard(self, workflow_id: str) -> Optional[str]:
        """Get the shard_id for a workflow."""
        with self._lock:
            return self._workflow_assignments.get(workflow_id)

    async def reassign_shard(self, workflow_id: str) -> str:
        """Reassign a workflow to a new shard."""
        with self._lock:
            old_shard_id = self._workflow_assignments.pop(workflow_id, None)
            if old_shard_id and old_shard_id in self._shards:
                self._shards[old_shard_id].workflow_count = max(
                    0, self._shards[old_shard_id].workflow_count - 1
                )
        return await self.assign_shard(workflow_id)

    # ------------------------------------------------------------------
    # Worker assignment
    # ------------------------------------------------------------------

    async def assign_worker_to_shard(self, shard_id: str, node_id: str) -> bool:
        """Assign a worker to a shard."""
        with self._lock:
            shard = self._shards.get(shard_id)
            if shard is None:
                return False
            shard.worker_node_id = node_id
        return True

    async def get_shard_worker(self, shard_id: str) -> Optional[str]:
        """Get the worker assigned to a shard."""
        with self._lock:
            shard = self._shards.get(shard_id)
            return shard.worker_node_id if shard else None

    # ------------------------------------------------------------------
    # Shard computation
    # ------------------------------------------------------------------

    def _hash_shard(self, key: str) -> str:
        """Consistent hash-based shard selection."""
        h = hashlib.md5(key.encode()).hexdigest()
        idx = int(h, 16) % self._shard_count
        return f"shard-{idx:04d}"

    def _range_shard(self, key: str) -> str:
        """Range-based shard selection (fallback to hash)."""
        return self._hash_shard(key)

    def _dynamic_shard(self) -> str:
        """Select the shard with the fewest workflows."""
        if not self._shards:
            return "shard-0000"
        return min(self._shards.values(), key=lambda s: s.workflow_count).shard_id

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_shards(self) -> List[Shard]:
        with self._lock:
            return list(self._shards.values())

    async def get_shard_info(self, shard_id: str) -> Optional[Shard]:
        with self._lock:
            return self._shards.get(shard_id)

    async def shard_distribution(self) -> Dict[str, int]:
        """Return workflow count per shard."""
        with self._lock:
            return {sid: s.workflow_count for sid, s in self._shards.items()}

    async def total_workflows(self) -> int:
        with self._lock:
            return sum(s.workflow_count for s in self._shards.values())

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "shard_count": self._shard_count,
                "strategy": self._strategy.value,
                "total_workflows": sum(s.workflow_count for s in self._shards.values()),
                "assigned_workflows": len(self._workflow_assignments),
                "shards": {
                    sid: {"workflow_count": s.workflow_count, "worker": s.worker_node_id}
                    for sid, s in self._shards.items()
                },
            }
