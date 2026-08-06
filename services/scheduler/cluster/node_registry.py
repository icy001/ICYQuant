"""Node Registry — cluster-wide node registration and discovery.

The :class:`NodeRegistry` maintains the authoritative list of scheduler
nodes in the cluster, tracks their status, and provides lookup services.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .scheduler_node import SchedulerNode

logger = logging.getLogger(__name__)


class NodeStatus:
    """Possible node status values."""

    ONLINE = "online"
    OFFLINE = "offline"
    SUSPECT = "suspect"
    DRAINING = "draining"
    REMOVED = "removed"


class NodeRegistry:
    """Cluster-wide node registration and discovery service.

    Usage::

        registry = NodeRegistry()
        await registry.register(node_id="scheduler-1", cluster_name="icyquant")
        node = registry.get("scheduler-1")
        online_nodes = registry.list_online()
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, SchedulerNode] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def register(
        self,
        node_id: str,
        *,
        cluster_name: str = "icyquant-scheduler",
        metadata: Optional[Dict[str, Any]] = None,
        host: str = "localhost",
        port: int = 8001,
        labels: Optional[Dict[str, str]] = None,
    ) -> SchedulerNode:
        """Register a new node or re-register an existing one."""
        with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                node.status = NodeStatus.ONLINE
                node.heartbeat()
                logger.debug("Re-registered existing node %s", node_id)
                return node

            node = SchedulerNode(
                node_id=node_id,
                host=host,
                port=port,
                labels=labels or {},
            )
            node.status = NodeStatus.ONLINE
            node.heartbeat()
            self._nodes[node_id] = node
            logger.info("Registered node %s in cluster %s", node_id, cluster_name)
            return node

    async def deregister(self, node_id: str) -> None:
        """Remove a node from the registry."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.REMOVED
                del self._nodes[node_id]
                logger.info("Deregistered node %s", node_id)

    async def sync(self) -> None:
        """Synchronize the registry (placeholder for distributed sync)."""
        logger.debug("Node registry sync requested")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, node_id: str) -> Optional[SchedulerNode]:
        """Get a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_all(self) -> List[SchedulerNode]:
        """List all registered nodes."""
        with self._lock:
            return list(self._nodes.values())

    def list_online(self) -> List[SchedulerNode]:
        """List nodes that are currently online."""
        with self._lock:
            return [n for n in self._nodes.values() if n.status == NodeStatus.ONLINE]

    def list_by_role(self, role: str) -> List[SchedulerNode]:
        """List nodes by their cluster role."""
        with self._lock:
            return [n for n in self._nodes.values() if n.role == role]

    def list_by_label(self, key: str, value: str) -> List[SchedulerNode]:
        """List nodes matching a specific label."""
        with self._lock:
            return [n for n in self._nodes.values() if n.labels.get(key) == value]

    def count(self) -> int:
        """Total number of registered nodes."""
        with self._lock:
            return len(self._nodes)

    def count_online(self) -> int:
        """Number of online nodes."""
        return len(self.list_online())

    def get_leader(self) -> Optional[SchedulerNode]:
        """Get the current leader node, if any."""
        leaders = self.list_by_role("leader")
        return leaders[0] if leaders else None

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def lookup(self, endpoint: str) -> Optional[str]:
        """Lookup a node ID by its endpoint address."""
        with self._lock:
            for node in self._nodes.values():
                if node.endpoint == endpoint:
                    return node.node_id
        return None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def mark_suspect(self, node_id: str) -> None:
        """Mark a node as suspect (potential failure)."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.SUSPECT
                logger.warning("Node %s marked as suspect", node_id)

    def mark_offline(self, node_id: str) -> None:
        """Mark a node as offline."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.OFFLINE
                logger.warning("Node %s marked as offline", node_id)

    def mark_online(self, node_id: str) -> None:
        """Mark a node as online."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.ONLINE
                self._nodes[node_id].heartbeat()

    def get_registry_info(self) -> Dict[str, Any]:
        """Return registry status summary."""
        online = self.list_online()
        return {
            "total_nodes": self.count(),
            "online_nodes": len(online),
            "offline_nodes": self.count() - len(online),
            "leader_id": self.get_leader().node_id if self.get_leader() else None,
            "nodes": {n.node_id: n.to_dict() for n in self.list_all()},
        }
