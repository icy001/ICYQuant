"""Worker Registry — tracks worker node resource state for intelligent scheduling.

Records per-worker metrics:

* CPU usage / cores
* Memory usage / total
* Queue length (pending tasks)
* Current active tasks
* Average task latency
* Last heartbeat time

These metrics drive the scheduler's placement decisions and load balancing.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .cluster_node import NodeResources

logger = logging.getLogger(__name__)


@dataclass
class WorkerRecord:
    """Resource and performance record for a worker node."""

    node_id: str
    resources: NodeResources = field(default_factory=NodeResources)
    queue_length: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_latency_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    is_available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def load_score(self) -> float:
        """Composite load score (0.0 = idle, 1.0 = fully loaded)."""
        cpu_weight = 0.4
        mem_weight = 0.3
        queue_weight = 0.3

        cpu_score = self.resources.cpu_usage_pct / 100.0
        mem_score = self.resources.memory_usage_pct / 100.0
        queue_score = min(1.0, self.queue_length / 100.0)

        return cpu_weight * cpu_score + mem_weight * mem_score + queue_weight * queue_score

    @property
    def available_capacity(self) -> float:
        """Available capacity ratio (0.0 = full, 1.0 = empty)."""
        return 1.0 - self.load_score

    def update_resources(self, resources: NodeResources) -> None:
        self.resources = resources
        self.last_updated = datetime.utcnow()

    def record_task_started(self) -> None:
        self.active_tasks += 1
        self.queue_length = max(0, self.queue_length - 1)

    def record_task_completed(self, *, latency_ms: float = 0.0) -> None:
        self.active_tasks = max(0, self.active_tasks - 1)
        self.completed_tasks += 1
        if latency_ms > 0:
            total = self.avg_latency_ms * (self.completed_tasks - 1) + latency_ms
            self.avg_latency_ms = total / self.completed_tasks

    def record_task_failed(self) -> None:
        self.active_tasks = max(0, self.active_tasks - 1)
        self.failed_tasks += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "resources": self.resources.to_dict(),
            "queue_length": self.queue_length,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_latency_ms": self.avg_latency_ms,
            "load_score": self.load_score,
            "available_capacity": self.available_capacity,
            "last_updated": self.last_updated.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "is_available": self.is_available,
        }


class WorkerRegistry:
    """Registry of worker nodes with resource tracking for scheduling.

    Usage::

        registry = WorkerRegistry()
        await registry.start()
        await registry.register_worker("node_abc", resources=...)
        best = await registry.select_best_worker()
    """

    def __init__(self, *, max_workers: int = 1000) -> None:
        self._max_workers = max_workers
        self._lock = threading.RLock()
        self._workers: Dict[str, WorkerRecord] = {}
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("WorkerRegistry: started (max_workers=%d)", self._max_workers)

    async def stop(self) -> None:
        self._started = False
        with self._lock:
            self._workers.clear()
        logger.info("WorkerRegistry: stopped")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_worker(
        self,
        node_id: str,
        *,
        resources: Optional[NodeResources] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Register or update a worker."""
        with self._lock:
            if len(self._workers) >= self._max_workers and node_id not in self._workers:
                logger.warning("WorkerRegistry: at capacity")
                return False

            if node_id not in self._workers:
                self._workers[node_id] = WorkerRecord(
                    node_id=node_id,
                    resources=resources or NodeResources(),
                    metadata=metadata or {},
                )
            else:
                record = self._workers[node_id]
                if resources:
                    record.update_resources(resources)
                if metadata:
                    record.metadata.update(metadata)
                record.last_heartbeat = datetime.utcnow()
                record.is_available = True
        return True

    async def deregister_worker(self, node_id: str) -> bool:
        """Remove a worker."""
        with self._lock:
            return self._workers.pop(node_id, None) is not None

    async def mark_unavailable(self, node_id: str) -> None:
        """Mark a worker as unavailable."""
        with self._lock:
            record = self._workers.get(node_id)
            if record:
                record.is_available = False

    async def mark_available(self, node_id: str) -> None:
        """Mark a worker as available."""
        with self._lock:
            record = self._workers.get(node_id)
            if record:
                record.is_available = True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_worker(self, node_id: str) -> Optional[WorkerRecord]:
        with self._lock:
            return self._workers.get(node_id)

    async def list_workers(self, *, available_only: bool = True) -> List[WorkerRecord]:
        with self._lock:
            workers = list(self._workers.values())
            if available_only:
                workers = [w for w in workers if w.is_available]
            return workers

    async def count_workers(self, *, available_only: bool = True) -> int:
        workers = await self.list_workers(available_only=available_only)
        return len(workers)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    async def select_best_worker(self) -> Optional[str]:
        """Select the best worker based on lowest load score.

        Returns the node_id of the best worker, or None if none available.
        """
        workers = await self.list_workers(available_only=True)
        if not workers:
            return None

        # Sort by load_score ascending (least loaded first)
        workers.sort(key=lambda w: w.load_score)
        return workers[0].node_id

    async def select_workers(
        self,
        count: int = 1,
        *,
        min_available_capacity: float = 0.0,
    ) -> List[str]:
        """Select the top N workers by load score.

        Returns node_ids sorted from least to most loaded.
        """
        workers = await self.list_workers(available_only=True)
        workers = [w for w in workers if w.available_capacity >= min_available_capacity]
        workers.sort(key=lambda w: w.load_score)
        return [w.node_id for w in workers[:count]]

    async def get_cluster_load(self) -> Dict[str, float]:
        """Get aggregate cluster load metrics."""
        workers = await self.list_workers(available_only=True)
        if not workers:
            return {"avg_load": 0.0, "total_active_tasks": 0, "total_queue_length": 0}

        avg_load = sum(w.load_score for w in workers) / len(workers)
        total_active = sum(w.active_tasks for w in workers)
        total_queue = sum(w.queue_length for w in workers)
        return {
            "avg_load": round(avg_load, 4),
            "total_active_tasks": total_active,
            "total_queue_length": total_queue,
            "worker_count": len(workers),
        }

    # ------------------------------------------------------------------
    # Task tracking
    # ------------------------------------------------------------------

    async def record_task_dispatched(self, node_id: str) -> None:
        with self._lock:
            record = self._workers.get(node_id)
            if record:
                record.record_task_started()

    async def record_task_completed(self, node_id: str, *, latency_ms: float = 0.0) -> None:
        with self._lock:
            record = self._workers.get(node_id)
            if record:
                record.record_task_completed(latency_ms=latency_ms)

    async def record_task_failed(self, node_id: str) -> None:
        with self._lock:
            record = self._workers.get(node_id)
            if record:
                record.record_task_failed()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            available = [w for w in self._workers.values() if w.is_available]
            return {
                "total_workers": len(self._workers),
                "available_workers": len(available),
                "workers": [w.to_dict() for w in available[:20]],  # Limit output
            }
