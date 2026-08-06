"""Resource Tracker — tracks active resource allocations.

The :class:`ResourceTracker` maintains a ledger of all active allocations:
who holds what, on which node, for how long.  It is used by the reclaimer
and for auditing.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AllocationRecord:
    """Record of a single resource allocation."""

    allocation_id: str
    job_id: str
    schedule_id: str
    node_id: str
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    gpu_units: float = 0.0
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.allocated_at).total_seconds()


class ResourceTracker:
    """Tracks all active resource allocations.

    Usage::

        tracker = ResourceTracker()
        tracker.record("alloc-1", "job-1", "node-1", cpu_cores=2, memory_mb=4096)
        rec = tracker.get("alloc-1")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._allocations: Dict[str, AllocationRecord] = {}
        self._by_node: Dict[str, List[str]] = {}
        self._by_job: Dict[str, List[str]] = {}

        self._total_allocations: int = 0
        self._total_released: int = 0

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def record(
        self, allocation_id: str, job_id: str, node_id: str,
        schedule_id: str = "", cpu_cores: float = 0.0,
        memory_mb: float = 0.0, gpu_units: float = 0.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> AllocationRecord:
        rec = AllocationRecord(
            allocation_id=allocation_id, job_id=job_id,
            schedule_id=schedule_id, node_id=node_id,
            cpu_cores=cpu_cores, memory_mb=memory_mb,
            gpu_units=gpu_units, labels=labels or {},
        )
        with self._lock:
            self._allocations[allocation_id] = rec
            self._by_node.setdefault(node_id, []).append(allocation_id)
            self._by_job.setdefault(job_id, []).append(allocation_id)
            self._total_allocations += 1
        return rec

    def remove(self, allocation_id: str) -> Optional[AllocationRecord]:
        with self._lock:
            rec = self._allocations.pop(allocation_id, None)
            if rec is None:
                return None
            if rec.node_id in self._by_node:
                self._by_node[rec.node_id] = [
                    a for a in self._by_node[rec.node_id] if a != allocation_id
                ]
            if rec.job_id in self._by_job:
                self._by_job[rec.job_id] = [
                    a for a in self._by_job[rec.job_id] if a != allocation_id
                ]
            self._total_released += 1
            return rec

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, allocation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._allocations.get(allocation_id)
            if rec is None:
                return None
            return {
                "allocation_id": rec.allocation_id,
                "job_id": rec.job_id,
                "node_id": rec.node_id,
                "cpu_cores": rec.cpu_cores,
                "memory_mb": rec.memory_mb,
                "gpu_units": rec.gpu_units,
                "allocated_at": rec.allocated_at.isoformat(),
                "age_seconds": rec.age_seconds,
            }

    def get_by_node(self, node_id: str) -> List[AllocationRecord]:
        with self._lock:
            ids = self._by_node.get(node_id, [])
            return [self._allocations[aid] for aid in ids if aid in self._allocations]

    def get_by_job(self, job_id: str) -> List[AllocationRecord]:
        with self._lock:
            ids = self._by_job.get(job_id, [])
            return [self._allocations[aid] for aid in ids if aid in self._allocations]

    def get_node_allocation_summary(self, node_id: str) -> Dict[str, float]:
        recs = self.get_by_node(node_id)
        return {
            "cpu_total": sum(r.cpu_cores for r in recs),
            "memory_total_mb": sum(r.memory_mb for r in recs),
            "gpu_total": sum(r.gpu_units for r in recs),
            "allocation_count": len(recs),
        }

    def count(self) -> int:
        return len(self._allocations)

    def list_all(self) -> List[AllocationRecord]:
        with self._lock:
            return list(self._allocations.values())

    def find_expired(self) -> List[AllocationRecord]:
        """Return allocations that have exceeded their expiry time."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                r for r in self._allocations.values()
                if r.expires_at is not None and r.expires_at <= now
            ]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_allocations": len(self._allocations),
                "total_allocations": self._total_allocations,
                "total_released": self._total_released,
                "nodes_with_allocations": len(self._by_node),
                "jobs_with_allocations": len(self._by_job),
            }
