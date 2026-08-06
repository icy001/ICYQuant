"""Resource Pool — cluster-wide resource inventory.

The :class:`ResourcePool` maintains the total and available capacity of
every node in the cluster.  It is the source of truth for capacity queries
used by all placement and scheduling decisions.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class _NodeResources:
    """Per-node resource snapshot."""

    node_id: str
    cpu_total: float = 0.0
    cpu_used: float = 0.0
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    gpu_total: float = 0.0
    gpu_used: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    concurrency_max: int = 100
    concurrency_used: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def cpu_available(self) -> float:
        return max(0.0, self.cpu_total - self.cpu_used)

    @property
    def memory_available_mb(self) -> float:
        return max(0.0, self.memory_total_mb - self.memory_used_mb)

    @property
    def gpu_available(self) -> float:
        return max(0.0, self.gpu_total - self.gpu_used)

    @property
    def cpu_utilization(self) -> float:
        return self.cpu_used / max(self.cpu_total, 0.001)

    @property
    def memory_utilization(self) -> float:
        return self.memory_used_mb / max(self.memory_total_mb, 0.001)


class ResourcePool:
    """Cluster-wide resource inventory.

    Tracks every node's capacity and usage.  Thread-safe.

    Usage::

        pool = ResourcePool()
        pool.add_node("node-1", cpu=16, memory_mb=32_768, gpu=2)
        pool.allocate("node-1", cpu_cores=2, memory_mb=4096)
        print(pool.utilization())
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, _NodeResources] = {}
        self._version: int = 0

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    def add_node(
        self, node_id: str, cpu: float = 0, memory_mb: float = 0,
        gpu: float = 0, labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._nodes[node_id] = _NodeResources(
                node_id=node_id, cpu_total=cpu, memory_total_mb=memory_mb,
                gpu_total=gpu, labels=labels or {},
            )
            self._version += 1

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            self._nodes.pop(node_id, None)
            self._version += 1

    def update_node(
        self, node_id: str, cpu: Optional[float] = None,
        memory_mb: Optional[float] = None, gpu: Optional[float] = None,
    ) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return
            if cpu is not None:
                node.cpu_total = cpu
            if memory_mb is not None:
                node.memory_total_mb = memory_mb
            if gpu is not None:
                node.gpu_total = gpu
            self._version += 1

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate(
        self, node_id: str, cpu_cores: float = 0.0,
        memory_mb: float = 0.0, gpu_units: float = 0.0,
    ) -> bool:
        """Attempt to allocate resources on a node. Returns False if insufficient."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            if cpu_cores > node.cpu_available:
                return False
            if memory_mb > node.memory_available_mb:
                return False
            if gpu_units > node.gpu_available:
                return False
            node.cpu_used += cpu_cores
            node.memory_used_mb += memory_mb
            node.gpu_used += gpu_units
            self._version += 1
            return True

    def release(
        self, node_id: str, cpu_cores: float = 0.0,
        memory_mb: float = 0.0, gpu_units: float = 0.0,
    ) -> None:
        """Release resources back to a node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return
            node.cpu_used = max(0.0, node.cpu_used - cpu_cores)
            node.memory_used_mb = max(0.0, node.memory_used_mb - memory_mb)
            node.gpu_used = max(0.0, node.gpu_used - gpu_units)
            self._version += 1

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[_NodeResources]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> List[_NodeResources]:
        with self._lock:
            return list(self._nodes.values())

    def get_nodes_by_label(self, key: str, value: str) -> List[_NodeResources]:
        with self._lock:
            return [
                n for n in self._nodes.values()
                if n.labels.get(key) == value
            ]

    def find_best_node(
        self, cpu_cores: float, memory_mb: float, gpu: float = 0.0,
    ) -> Optional[str]:
        """Find the node with the most available capacity that meets requirements."""
        with self._lock:
            best: Optional[str] = None
            best_avail = -1.0
            for n in self._nodes.values():
                if (
                    n.cpu_available >= cpu_cores
                    and n.memory_available_mb >= memory_mb
                    and n.gpu_available >= gpu
                ):
                    score = n.cpu_available + n.memory_available_mb / 1024
                    if score > best_avail:
                        best_avail = score
                        best = n.node_id
            return best

    def total_capacity(self) -> Dict[str, float]:
        with self._lock:
            return {
                "cpu_total": sum(n.cpu_total for n in self._nodes.values()),
                "cpu_used": sum(n.cpu_used for n in self._nodes.values()),
                "memory_total_mb": sum(n.memory_total_mb for n in self._nodes.values()),
                "memory_used_mb": sum(n.memory_used_mb for n in self._nodes.values()),
                "gpu_total": sum(n.gpu_total for n in self._nodes.values()),
                "gpu_used": sum(n.gpu_used for n in self._nodes.values()),
                "node_count": len(self._nodes),
            }

    def utilization(self) -> Dict[str, float]:
        caps = self.total_capacity()
        return {
            "cpu_pct": caps["cpu_used"] / max(caps["cpu_total"], 0.001) * 100,
            "memory_pct": caps["memory_used_mb"] / max(caps["memory_total_mb"], 0.001) * 100,
            "gpu_pct": caps["gpu_used"] / max(caps["gpu_total"], 0.001) * 100,
            "node_count": caps["node_count"],
        }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": self.total_capacity(),
                "utilization": self.utilization(),
                "nodes": {
                    n.node_id: {
                        "cpu": f"{n.cpu_used:.1f}/{n.cpu_total:.1f}",
                        "memory": f"{n.memory_used_mb:.0f}/{n.memory_total_mb:.0f}",
                        "gpu": f"{n.gpu_used:.0f}/{n.gpu_total:.0f}",
                        "labels": n.labels,
                    }
                    for n in self._nodes.values()
                },
            }

    def health_report(self) -> Dict[str, Any]:
        return self.status()
