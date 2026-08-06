"""Resource Reclaimer — releases resources after job completion.

The :class:`ResourceReclaimer` handles resource cleanup: releasing CPU,
memory, and GPU back to the pool, removing tracker records, and updating
quota usage.  Also supports cluster-wide rebalancing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .resource_pool import ResourcePool
from .resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)


class ResourceReclaimer:
    """Releases and rebalances cluster resources.

    Usage::

        reclaimer = ResourceReclaimer(pool, tracker)
        await reclaimer.release("alloc-abc123")
    """

    def __init__(self, pool: ResourcePool, tracker: ResourceTracker) -> None:
        self._pool = pool
        self._tracker = tracker

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    async def release(self, allocation_id: str) -> bool:
        """Release a single allocation."""
        rec = self._tracker.remove(allocation_id)
        if rec is None:
            return False

        self._pool.release(
            node_id=rec.node_id,
            cpu_cores=rec.cpu_cores,
            memory_mb=rec.memory_mb,
            gpu_units=rec.gpu_units,
        )
        logger.debug("ResourceReclaimer: released %s from %s", allocation_id, rec.node_id)
        return True

    async def release_batch(self, allocation_ids: List[str]) -> int:
        """Release multiple allocations. Returns count of successfully released."""
        count = 0
        for aid in allocation_ids:
            if await self.release(aid):
                count += 1
        return count

    async def release_by_job(self, job_id: str) -> int:
        """Release all allocations belonging to a job."""
        recs = self._tracker.get_by_job(job_id)
        return await self.release_batch([r.allocation_id for r in recs])

    async def release_by_node(self, node_id: str) -> int:
        """Release all allocations on a node."""
        recs = self._tracker.get_by_node(node_id)
        return await self.release_batch([r.allocation_id for r in recs])

    # ------------------------------------------------------------------
    # Reclaim all
    # ------------------------------------------------------------------

    async def reclaim_all(self) -> int:
        """Release every active allocation. Used during shutdown."""
        recs = self._tracker.list_all()
        count = await self.release_batch([r.allocation_id for r in recs])
        logger.info("ResourceReclaimer: reclaimed %d allocations", count)
        return count

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    async def rebalance(self) -> Dict[str, Any]:
        """Rebalance by releasing idle allocations and redistributing.

        A full rebalancing implementation would:
        1. Identify over-utilized nodes
        2. Migrate jobs to under-utilized nodes
        3. Evict low-priority allocations if needed
        """
        # Placeholder: identify expired allocations
        expired = self._tracker.find_expired()
        released = await self.release_batch([r.allocation_id for r in expired])

        return {
            "action": "rebalance",
            "expired_found": len(expired),
            "released": released,
        }

    def health_report(self) -> Dict[str, Any]:
        return {
            "active_allocations": self._tracker.count(),
        }
