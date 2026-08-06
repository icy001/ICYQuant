"""Node Inventory — registry of all cluster nodes with capabilities.

The :class:`NodeInventory` maintains a catalog of every node in the cluster,
its hardware capabilities, current status, and health metrics.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"
    MAINTENANCE = "maintenance"
    UNHEALTHY = "unhealthy"


@dataclass
class NodeRecord:
    """Record of a single cluster node."""

    node_id: str
    hostname: str = ""
    ip_address: str = ""
    status: NodeStatus = NodeStatus.ONLINE

    # Capacity
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    disk_gb: float = 0.0
    gpu_units: float = 0.0
    gpu_model: str = ""

    # Usage
    cpu_used: float = 0.0
    memory_used_mb: float = 0.0
    gpu_used: float = 0.0

    # Topology
    region: str = ""
    zone: str = ""
    rack: str = ""

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Health
    failure_count: int = 0
    avg_latency_ms: float = 0.0

    @property
    def cpu_available(self) -> float:
        return max(0.0, self.cpu_cores - self.cpu_used)

    @property
    def memory_available_mb(self) -> float:
        return max(0.0, self.memory_mb - self.memory_used_mb)

    @property
    def gpu_available(self) -> float:
        return max(0.0, self.gpu_units - self.gpu_used)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id, "hostname": self.hostname,
            "status": self.status.value, "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb, "gpu_units": self.gpu_units,
            "cpu_used": self.cpu_used, "memory_used_mb": self.memory_used_mb,
            "region": self.region, "zone": self.zone, "rack": self.rack,
            "labels": self.labels, "failure_count": self.failure_count,
            "avg_latency_ms": self.avg_latency_ms,
        }


class NodeInventory:
    """Catalog of all cluster nodes.

    Usage::

        inv = NodeInventory()
        inv.register(NodeRecord(node_id="n1", cpu_cores=16, region="us-east"))
        nodes = inv.filter(region="us-east", status=NodeStatus.ONLINE)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, NodeRecord] = {}
        self._version: int = 0

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, record: NodeRecord) -> None:
        with self._lock:
            self._nodes[record.node_id] = record
            self._version += 1

    def unregister(self, node_id: str) -> bool:
        with self._lock:
            removed = self._nodes.pop(node_id, None)
            if removed:
                self._version += 1
            return removed is not None

    def update_status(self, node_id: str, status: NodeStatus) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.status = status
                self._version += 1

    def heartbeat(self, node_id: str, cpu_used: float = 0,
                  memory_used_mb: float = 0, gpu_used: float = 0) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.last_heartbeat = datetime.now(timezone.utc)
                node.cpu_used = cpu_used
                node.memory_used_mb = memory_used_mb
                node.gpu_used = gpu_used

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, node_id: str) -> Optional[NodeRecord]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_all(self) -> List[NodeRecord]:
        with self._lock:
            return list(self._nodes.values())

    def filter(
        self, region: Optional[str] = None, zone: Optional[str] = None,
        status: Optional[NodeStatus] = None, min_cpu: float = 0.0,
        min_memory_mb: float = 0.0, gpu_required: bool = False,
        labels: Optional[Dict[str, str]] = None,
    ) -> List[NodeRecord]:
        """Filter nodes by multiple criteria."""
        with self._lock:
            result = list(self._nodes.values())

        if region:
            result = [n for n in result if n.region == region]
        if zone:
            result = [n for n in result if n.zone == zone]
        if status:
            result = [n for n in result if n.status == status]
        if min_cpu:
            result = [n for n in result if n.cpu_available >= min_cpu]
        if min_memory_mb:
            result = [n for n in result if n.memory_available_mb >= min_memory_mb]
        if gpu_required:
            result = [n for n in result if n.gpu_available > 0]
        if labels:
            for k, v in labels.items():
                result = [n for n in result if n.labels.get(k) == v]

        return result

    def count(self) -> int:
        return len(self._nodes)

    def count_by_status(self) -> Dict[str, int]:
        with self._lock:
            counts: Dict[str, int] = {}
            for n in self._nodes.values():
                counts[n.status.value] = counts.get(n.status.value, 0) + 1
            return counts

    def find_stale(self, timeout_seconds: float = 60.0) -> List[NodeRecord]:
        """Find nodes that haven't sent a heartbeat recently."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                n for n in self._nodes.values()
                if (now - n.last_heartbeat).total_seconds() > timeout_seconds
            ]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "by_status": self.count_by_status(),
            "version": self._version,
        }
