"""Cluster Node — represents a single node in the distributed workflow cluster.

Each node has a unique ID, role (leader / worker), and carries resource
capabilities used for intelligent task placement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeRole(str, Enum):
    """The role a node plays in the workflow cluster."""

    LEADER = "leader"
    WORKER = "worker"
    COORDINATOR = "coordinator"
    OBSERVER = "observer"


class NodeStatus(str, Enum):
    """Current lifecycle status of a node."""

    JOINING = "joining"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPECT = "suspect"
    LEAVING = "leaving"
    LEFT = "left"
    UNREACHABLE = "unreachable"

    @property
    def is_available(self) -> bool:
        return self in (NodeStatus.ACTIVE, NodeStatus.DEGRADED)

    @property
    def is_terminal(self) -> bool:
        return self in (NodeStatus.LEFT, NodeStatus.UNREACHABLE)


@dataclass
class NodeResources:
    """Resource snapshot for a cluster node."""

    cpu_cores: float = 0.0
    cpu_usage_pct: float = 0.0
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    disk_total_mb: float = 0.0
    disk_used_mb: float = 0.0
    network_mbps: float = 0.0
    active_tasks: int = 0
    max_tasks: int = 100

    @property
    def memory_usage_pct(self) -> float:
        if self.memory_total_mb <= 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb) * 100.0

    @property
    def cpu_available(self) -> float:
        return self.cpu_cores * (1.0 - self.cpu_usage_pct / 100.0)

    @property
    def memory_available_mb(self) -> float:
        return max(0.0, self.memory_total_mb - self.memory_used_mb)

    @property
    def task_capacity_ratio(self) -> float:
        if self.max_tasks <= 0:
            return 1.0
        return 1.0 - (self.active_tasks / self.max_tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "cpu_usage_pct": self.cpu_usage_pct,
            "memory_total_mb": self.memory_total_mb,
            "memory_used_mb": self.memory_used_mb,
            "disk_total_mb": self.disk_total_mb,
            "disk_used_mb": self.disk_used_mb,
            "network_mbps": self.network_mbps,
            "active_tasks": self.active_tasks,
            "max_tasks": self.max_tasks,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeResources:
        return cls(
            cpu_cores=float(data.get("cpu_cores", 0.0)),
            cpu_usage_pct=float(data.get("cpu_usage_pct", 0.0)),
            memory_total_mb=float(data.get("memory_total_mb", 0.0)),
            memory_used_mb=float(data.get("memory_used_mb", 0.0)),
            disk_total_mb=float(data.get("disk_total_mb", 0.0)),
            disk_used_mb=float(data.get("disk_used_mb", 0.0)),
            network_mbps=float(data.get("network_mbps", 0.0)),
            active_tasks=int(data.get("active_tasks", 0)),
            max_tasks=int(data.get("max_tasks", 100)),
        )


@dataclass
class NodeCapabilities:
    """Declared capabilities of a cluster node."""

    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    features: List[str] = field(default_factory=list)
    supported_node_types: List[str] = field(default_factory=list)
    region: str = "default"
    zone: str = "default"

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def supports_node_type(self, node_type: str) -> bool:
        if not self.supported_node_types:
            return True  # Supports all by default
        return node_type in self.supported_node_types

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tags": list(self.tags),
            "labels": dict(self.labels),
            "features": list(self.features),
            "supported_node_types": list(self.supported_node_types),
            "region": self.region,
            "zone": self.zone,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeCapabilities:
        return cls(
            tags=list(data.get("tags", [])),
            labels=dict(data.get("labels", {})),
            features=list(data.get("features", [])),
            supported_node_types=list(data.get("supported_node_types", [])),
            region=data.get("region", "default"),
            zone=data.get("zone", "default"),
        )


@dataclass
class ClusterNode:
    """Represents a single node in the workflow cluster."""

    node_id: str
    host: str = "localhost"
    port: int = 9090
    role: NodeRole = NodeRole.WORKER
    status: NodeStatus = NodeStatus.JOINING
    resources: NodeResources = field(default_factory=NodeResources)
    capabilities: NodeCapabilities = field(default_factory=NodeCapabilities)
    metadata: Dict[str, Any] = field(default_factory=dict)
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None
    version: str = "0.4.0"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def is_leader(self) -> bool:
        return self.role == NodeRole.LEADER

    @property
    def is_worker(self) -> bool:
        return self.role == NodeRole.WORKER

    @property
    def is_available(self) -> bool:
        return self.status.is_available

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def update_status(self, status: NodeStatus) -> None:
        self.status = status

    def update_role(self, role: NodeRole) -> None:
        self.role = role

    def update_resources(self, resources: NodeResources) -> None:
        self.resources = resources

    def record_heartbeat(self) -> None:
        self.last_heartbeat = datetime.utcnow()
        if self.status == NodeStatus.SUSPECT:
            self.status = NodeStatus.ACTIVE

    def mark_unreachable(self) -> None:
        if self.status != NodeStatus.LEFT:
            self.status = NodeStatus.UNREACHABLE

    def mark_degraded(self) -> None:
        if self.status == NodeStatus.ACTIVE:
            self.status = NodeStatus.DEGRADED

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role.value,
            "status": self.status.value,
            "resources": self.resources.to_dict(),
            "capabilities": self.capabilities.to_dict(),
            "metadata": dict(self.metadata),
            "joined_at": self.joined_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClusterNode:
        joined_at = data.get("joined_at")
        last_heartbeat = data.get("last_heartbeat")
        return cls(
            node_id=data["node_id"],
            host=data.get("host", "localhost"),
            port=int(data.get("port", 9090)),
            role=NodeRole(data.get("role", "worker")),
            status=NodeStatus(data.get("status", "joining")),
            resources=NodeResources.from_dict(data.get("resources", {})),
            capabilities=NodeCapabilities.from_dict(data.get("capabilities", {})),
            metadata=dict(data.get("metadata", {})),
            joined_at=datetime.fromisoformat(joined_at) if joined_at else datetime.utcnow(),
            last_heartbeat=datetime.fromisoformat(last_heartbeat) if last_heartbeat else None,
            version=data.get("version", "0.4.0"),
        )

    def __repr__(self) -> str:
        return (
            f"ClusterNode(id={self.node_id!r}, role={self.role.value}, "
            f"status={self.status.value}, address={self.address})"
        )
