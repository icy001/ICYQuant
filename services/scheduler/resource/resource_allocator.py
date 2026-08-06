"""Resource Allocator — intelligent resource allocation with quota and reservation.

The :class:`ResourceAllocator` orchestrates the full allocation pipeline:
estimate → quota check → placement → reservation → commit.  It uses the
pool for capacity queries, tracker for record-keeping, and quota for
tenant enforcement.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .resource_pool import ResourcePool
from .resource_tracker import ResourceTracker
from .resource_quota import ResourceQuota
from ..resource_manager import ResourceRequest

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    """Result of a resource allocation attempt."""

    success: bool
    allocation_id: str = ""
    node_id: str = ""
    error: Optional[str] = None
    cpu_allocated: float = 0.0
    memory_allocated_mb: float = 0.0
    gpu_allocated: float = 0.0
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceAllocator:
    """Intelligent resource allocator.

    Pipeline: request → estimate → quota → best-node → reserve → commit

    Usage::

        allocator = ResourceAllocator(pool, tracker, quota)
        result = await allocator.allocate(request)
    """

    def __init__(
        self, pool: ResourcePool, tracker: ResourceTracker, quota: ResourceQuota,
    ) -> None:
        self._pool = pool
        self._tracker = tracker
        self._quota = quota

    # ------------------------------------------------------------------
    # Allocate
    # ------------------------------------------------------------------

    async def allocate(self, request: ResourceRequest) -> AllocationResult:
        """Run the full allocation pipeline."""
        tenant_id = request.labels.get("tenant", "default")

        # 1. Quota check
        if not self._quota.check(
            tenant_id, request.cpu_cores, request.memory_mb, request.gpu_units,
        ):
            return AllocationResult(
                success=False,
                error=f"Quota exceeded for tenant '{tenant_id}'",
            )

        # 2. Find best node
        node_id = self._pool.find_best_node(
            request.cpu_cores, request.memory_mb, request.gpu_units,
        )
        if node_id is None:
            return AllocationResult(
                success=False,
                error="No node with sufficient capacity",
            )

        # 3. Reserve on pool
        ok = self._pool.allocate(
            node_id, request.cpu_cores, request.memory_mb, request.gpu_units,
        )
        if not ok:
            return AllocationResult(
                success=False,
                error="Allocation to node failed (race condition)",
            )

        # 4. Record in tracker
        alloc_id = f"alloc-{uuid.uuid4().hex[:8]}"
        self._tracker.record(
            allocation_id=alloc_id, job_id=request.job_id, node_id=node_id,
            schedule_id=request.schedule_id,
            cpu_cores=request.cpu_cores, memory_mb=request.memory_mb,
            gpu_units=request.gpu_units, labels=request.labels,
        )

        # 5. Reserve in quota
        self._quota.reserve(
            tenant_id, request.cpu_cores, request.memory_mb, request.gpu_units,
        )

        logger.debug(
            "ResourceAllocator: allocated %s on node=%s cpu=%.1f mem=%.0fMB",
            alloc_id, node_id, request.cpu_cores, request.memory_mb,
        )
        return AllocationResult(
            success=True, allocation_id=alloc_id, node_id=node_id,
            cpu_allocated=request.cpu_cores, memory_allocated_mb=request.memory_mb,
            gpu_allocated=request.gpu_units,
        )

    async def allocate_batch(
        self, requests: List[ResourceRequest],
    ) -> List[AllocationResult]:
        """Allocate multiple requests (sequential for correctness)."""
        results = []
        for req in requests:
            results.append(await self.allocate(req))
        return results

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "pool_nodes": len(self._pool.list_nodes()),
            "active_allocations": self._tracker.count(),
        }
