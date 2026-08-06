"""Shard Allocator — allocates and rebalances shards across worker nodes.

Works with :class:`ShardManager` to ensure shards are evenly distributed
and automatically rebalanced when workers join or leave.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .shard_manager import ShardManager, Shard
from .worker_registry import WorkerRegistry

logger = logging.getLogger(__name__)


@dataclass
class ShardAllocation:
    """A record of a shard allocated to a worker."""

    shard_id: str
    node_id: str
    allocated_at: datetime = field(default_factory=datetime.utcnow)
    is_primary: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShardAllocator:
    """Allocates shards to worker nodes and rebalances as needed.

    Usage::

        allocator = ShardAllocator(shards=..., workers=...)
        await allocator.start()
        await allocator.allocate_all()
    """

    def __init__(
        self,
        *,
        shards: ShardManager,
        workers: WorkerRegistry,
        rebalance_interval_seconds: float = 30.0,
    ) -> None:
        self._shards = shards
        self._workers = workers
        self._rebalance_interval = rebalance_interval_seconds
        self._lock = threading.RLock()
        self._allocations: Dict[str, ShardAllocation] = {}  # shard_id → allocation
        self._started = False
        self._rebalance_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        logger.info("ShardAllocator: started")

    async def stop(self) -> None:
        self._started = False
        if self._rebalance_task:
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass
        logger.info("ShardAllocator: stopped")

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    async def allocate_all(self) -> Dict[str, str]:
        """Allocate all shards to available workers.

        Returns a dict of shard_id → node_id.
        """
        shards = await self._shards.list_shards()
        workers = await self._workers.list_workers(available_only=True)

        if not workers:
            logger.warning("ShardAllocator: no workers available for allocation")
            return {}

        result: Dict[str, str] = {}

        for i, shard in enumerate(shards):
            worker = workers[i % len(workers)]
            allocation = ShardAllocation(
                shard_id=shard.shard_id,
                node_id=worker.node_id,
            )
            with self._lock:
                self._allocations[shard.shard_id] = allocation
            await self._shards.assign_worker_to_shard(shard.shard_id, worker.node_id)
            result[shard.shard_id] = worker.node_id

        logger.info("ShardAllocator: allocated %d shards across %d workers",
                     len(result), len(workers))
        return result

    async def allocate_shard(self, shard_id: str) -> Optional[str]:
        """Allocate a single shard to the best available worker."""
        workers = await self._workers.list_workers(available_only=True)
        if not workers:
            return None

        # Pick the worker with the fewest shards
        with self._lock:
            shard_counts: Dict[str, int] = {}
            for alloc in self._allocations.values():
                shard_counts[alloc.node_id] = shard_counts.get(alloc.node_id, 0) + 1

            best_worker = min(workers, key=lambda w: shard_counts.get(w.node_id, 0))

            allocation = ShardAllocation(
                shard_id=shard_id,
                node_id=best_worker.node_id,
            )
            self._allocations[shard_id] = allocation

        await self._shards.assign_worker_to_shard(shard_id, best_worker.node_id)
        return best_worker.node_id

    async def deallocate_shard(self, shard_id: str) -> None:
        """Remove a shard allocation."""
        with self._lock:
            self._allocations.pop(shard_id, None)

    async def get_allocation(self, shard_id: str) -> Optional[ShardAllocation]:
        with self._lock:
            return self._allocations.get(shard_id)

    async def get_worker_shards(self, node_id: str) -> List[str]:
        with self._lock:
            return [a.shard_id for a in self._allocations.values() if a.node_id == node_id]

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    async def rebalance(self) -> Dict[str, Any]:
        """Rebalance shards across workers for even distribution."""
        workers = await self._workers.list_workers(available_only=True)
        if not workers:
            return {"rebalanced": False, "reason": "No workers"}

        shards = await self._shards.list_shards()
        worker_count = len(workers)
        shards_per_worker = max(1, len(shards) // worker_count)

        with self._lock:
            # Count shards per worker
            counts: Dict[str, int] = {}
            for alloc in self._allocations.values():
                counts[alloc.node_id] = counts.get(alloc.node_id, 0) + 1

            migrations = 0
            for shard in shards:
                if shard.shard_id not in self._allocations:
                    continue
                alloc = self._allocations[shard.shard_id]
                if counts.get(alloc.node_id, 0) > shards_per_worker + 1:
                    # Move to least loaded worker
                    target = min(workers, key=lambda w: counts.get(w.node_id, 0))
                    if target.node_id != alloc.node_id:
                        alloc.node_id = target.node_id
                        counts[alloc.node_id] = counts.get(alloc.node_id, 0) + 1
                        counts[target.node_id] = counts.get(target.node_id, 0) + 1
                        await self._shards.assign_worker_to_shard(shard.shard_id, target.node_id)
                        migrations += 1

        logger.info("ShardAllocator: rebalanced, %d migrations", migrations)
        return {"rebalanced": True, "migrations": migrations}

    async def _rebalance_loop(self) -> None:
        while self._started:
            try:
                await asyncio.sleep(self._rebalance_interval)
                await self.rebalance()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ShardAllocator: error in rebalance loop")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "allocated_shards": len(self._allocations),
                "rebalance_interval": self._rebalance_interval,
            }
