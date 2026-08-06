"""Scheduler Node — representation of a single scheduler cluster node.

The :class:`SchedulerNode` models a single scheduler instance within
the cluster, holding its identity, role, capacity, and runtime state.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .coordinator import CoordinatorRole


class NodeRole:
    """Logical role of a scheduler node within the cluster."""

    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    OBSERVER = "observer"
    STANDBY = "standby"


class SchedulerNode:
    """Represents a single scheduler instance in the cluster.

    Usage::

        node = SchedulerNode(
            node_id="scheduler-1",
            host="10.0.0.1",
            port=8001,
            capacity={"cpu": 4, "memory_gb": 8},
        )
    """

    def __init__(
        self,
        node_id: str,
        *,
        host: str = "localhost",
        port: int = 8001,
        capacity: Optional[Dict[str, float]] = None,
        labels: Optional[Dict[str, str]] = None,
        zone: str = "default",
        region: str = "default",
    ) -> None:
        self.node_id: str = node_id
        self.host: str = host
        self.port: int = port
        self.capacity: Dict[str, float] = capacity or {"cpu": 1, "memory_gb": 1}
        self.labels: Dict[str, str] = labels or {}
        self.zone: str = zone
        self.region: str = region

        self.role: str = NodeRole.FOLLOWER
        self.status: str = "offline"
        self._lock = threading.Lock()

        self._created_at: datetime = datetime.now(timezone.utc)
        self._last_heartbeat: Optional[datetime] = None
        self._version: int = 0
        self._metrics: Dict[str, float] = {}
        self._assigned_shards: List[int] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def last_heartbeat(self) -> Optional[datetime]:
        return self._last_heartbeat

    @property
    def version(self) -> int:
        return self._version

    @property
    def is_leader(self) -> bool:
        return self.role == NodeRole.LEADER

    @property
    def is_online(self) -> bool:
        return self.status == "online"

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def assigned_shards(self) -> List[int]:
        return list(self._assigned_shards)

    # ------------------------------------------------------------------
    # State Updates
    # ------------------------------------------------------------------

    def heartbeat(self, metrics: Optional[Dict[str, float]] = None) -> None:
        """Record a heartbeat and optional metrics snapshot."""
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
            self.status = "online"
            if metrics:
                self._metrics.update(metrics)
            self._version += 1

    def set_role(self, role: str) -> None:
        """Update the node's cluster role."""
        with self._lock:
            self.role = role
            self._version += 1

    def set_status(self, status: str) -> None:
        """Update the node's online status."""
        with self._lock:
            self.status = status
            self._version += 1

    def update_capacity(self, capacity: Dict[str, float]) -> None:
        """Update the node's reported capacity."""
        with self._lock:
            self.capacity.update(capacity)
            self._version += 1

    def assign_shards(self, shards: List[int]) -> None:
        """Assign queue shards to this node."""
        with self._lock:
            self._assigned_shards = list(shards)
            self._version += 1

    def get_metrics(self) -> Dict[str, float]:
        """Return the latest metrics snapshot."""
        with self._lock:
            return dict(self._metrics)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary."""
        with self._lock:
            return {
                "node_id": self.node_id,
                "host": self.host,
                "port": self.port,
                "endpoint": self.endpoint,
                "role": self.role,
                "status": self.status,
                "capacity": dict(self.capacity),
                "labels": dict(self.labels),
                "zone": self.zone,
                "region": self.region,
                "version": self._version,
                "created_at": self._created_at.isoformat(),
                "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
                "metrics": dict(self._metrics),
                "assigned_shards": list(self._assigned_shards),
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulerNode":
        """Deserialize node from dictionary."""
        node = cls(
            node_id=data["node_id"],
            host=data.get("host", "localhost"),
            port=data.get("port", 8001),
            capacity=data.get("capacity"),
            labels=data.get("labels"),
            zone=data.get("zone", "default"),
            region=data.get("region", "default"),
        )
        node.role = data.get("role", NodeRole.FOLLOWER)
        node.status = data.get("status", "offline")
        node._version = data.get("version", 0)
        node._assigned_shards = data.get("assigned_shards", [])
        return node
