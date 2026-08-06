"""Resource Manager — unified entry point for resource-aware scheduling.

The :class:`ResourceManager` coordinates resource allocation, tracking,
pooling, monitoring, and rebalancing. It is the top-level facade that
the scheduler engine calls into for all resource decisions.

Pipeline::

    allocate → quota check → reserve → assign → track → release
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .resource_pool import ResourcePool
from .resource_tracker import ResourceTracker
from .resource_quota import ResourceQuota
from .resource_allocator import ResourceAllocator, AllocationResult
from .resource_reclaimer import ResourceReclaimer

logger = logging.getLogger(__name__)


class ResourceManagerState:
    UNINITIALIZED = "uninitialized"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


@dataclass
class ResourceRequest:
    """A single resource allocation request."""

    request_id: str
    job_id: str = ""
    schedule_id: str = ""
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    disk_gb: float = 0.0
    gpu_units: float = 0.0
    priority: int = 50
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class ResourceManager:
    """Unified entry point for resource-aware scheduling.

    Owns the pool, tracker, quota, allocator, and reclaimer. The scheduler
    engine calls allocate/release/rebalance through this facade.

    Usage::

        mgr = ResourceManager()
        await mgr.start()
        result = await mgr.allocate(request)
        await mgr.release(result.allocation_id)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: str = ResourceManagerState.UNINITIALIZED

        self._pool = ResourcePool()
        self._tracker = ResourceTracker()
        self._quota = ResourceQuota()
        self._allocator = ResourceAllocator(self._pool, self._tracker, self._quota)
        self._reclaimer = ResourceReclaimer(self._pool, self._tracker)

        self._started_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        with self._lock:
            self._state = ResourceManagerState.RUNNING
            self._started_at = datetime.now(timezone.utc)
        logger.info("ResourceManager: running")

    async def stop(self) -> None:
        with self._lock:
            self._state = ResourceManagerState.DRAINING
        await self._reclaimer.reclaim_all()
        with self._lock:
            self._state = ResourceManagerState.STOPPED
        logger.info("ResourceManager: stopped")

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    async def allocate(self, request: ResourceRequest) -> AllocationResult:
        """Allocate resources for a job."""
        if self._state != ResourceManagerState.RUNNING:
            return AllocationResult(success=False, error="ResourceManager not running")
        return await self._allocator.allocate(request)

    async def release(self, allocation_id: str) -> bool:
        """Release a previously allocated resource."""
        return await self._reclaimer.release(allocation_id)

    async def rebalance(self) -> Dict[str, Any]:
        """Trigger a cluster-wide resource rebalance."""
        return await self._reclaimer.rebalance()

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    def add_node(
        self, node_id: str, cpu: float = 0, memory_mb: float = 0,
        gpu: float = 0, labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self._pool.add_node(node_id, cpu, memory_mb, gpu, labels or {})

    def remove_node(self, node_id: str) -> None:
        self._pool.remove_node(node_id)

    def update_node_capacity(
        self, node_id: str, cpu: Optional[float] = None,
        memory_mb: Optional[float] = None, gpu: Optional[float] = None,
    ) -> None:
        self._pool.update_node(node_id, cpu, memory_mb, gpu)

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    def set_quota(self, tenant_id: str, max_cpu: float, max_memory_mb: float) -> None:
        self._quota.set_quota(tenant_id, max_cpu, max_memory_mb)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_pool_status(self) -> Dict[str, Any]:
        return self._pool.status()

    def get_allocation(self, allocation_id: str) -> Optional[Dict[str, Any]]:
        return self._tracker.get(allocation_id)

    def get_cluster_utilization(self) -> Dict[str, float]:
        return self._pool.utilization()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "pool": self._pool.health_report(),
            "tracker": self._tracker.health_report(),
            "quota": self._quota.health_report(),
        }
