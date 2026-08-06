"""Node Registry — maintains the cluster node directory.

Tracks for each node:

* Node ID, host, port
* Role (leader / worker / observer)
* Capabilities and resources
* Status (active / degraded / suspect / unreachable)

Supports dynamic join/leave and status updates.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .cluster_node import ClusterNode, NodeRole, NodeStatus

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Directory of all nodes in the workflow cluster.

    Usage::

        registry = NodeRegistry()
        await registry.start()
        await registry.register(node)
        nodes = await registry.list_nodes(role=NodeRole.WORKER)
    """

    def __init__(self, *, max_nodes: int = 100) -> None:
        self._max_nodes = max_nodes
        self._lock = threading.RLock()
        self._nodes: Dict[str, ClusterNode] = {}
        self._started = False

        # Callbacks
        self._on_join_callbacks: list = []
        self._on_leave_callbacks: list = []
        self._on_status_change_callbacks: list = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("NodeRegistry: started (max_nodes=%d)", self._max_nodes)

    async def stop(self) -> None:
        self._started = False
        with self._lock:
            self._nodes.clear()
        logger.info("NodeRegistry: stopped")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, node: ClusterNode) -> bool:
        """Register a node in the cluster. Returns False if at capacity."""
        with self._lock:
            if len(self._nodes) >= self._max_nodes and node.node_id not in self._nodes:
                logger.warning("NodeRegistry: at capacity (%d nodes)", self._max_nodes)
                return False

            is_new = node.node_id not in self._nodes
            self._nodes[node.node_id] = node

        if is_new:
            logger.info("NodeRegistry: node %s registered (role=%s)", node.node_id, node.role.value)
            for cb in self._on_join_callbacks:
                try:
                    cb(node)
                except Exception:
                    logger.exception("NodeRegistry: join callback error")
        return True

    async def deregister(self, node_id: str) -> bool:
        """Remove a node from the registry."""
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node is None:
                return False

        logger.info("NodeRegistry: node %s deregistered", node_id)
        for cb in self._on_leave_callbacks:
            try:
                cb(node)
            except Exception:
                logger.exception("NodeRegistry: leave callback error")
        return True

    async def update(self, node: ClusterNode) -> bool:
        """Update an existing node's state."""
        with self._lock:
            if node.node_id not in self._nodes:
                return False
            old = self._nodes[node.node_id]
            old_status = old.status
            self._nodes[node.node_id] = node

        if old_status != node.status:
            for cb in self._on_status_change_callbacks:
                try:
                    cb(node.node_id, old_status, node.status)
                except Exception:
                    logger.exception("NodeRegistry: status change callback error")
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get(self, node_id: str) -> Optional[ClusterNode]:
        """Retrieve a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    async def list_nodes(
        self,
        *,
        role: Optional[NodeRole] = None,
        status: Optional[NodeStatus] = None,
    ) -> List[ClusterNode]:
        """List nodes, optionally filtered by role and/or status."""
        with self._lock:
            results = []
            for node in self._nodes.values():
                if role and node.role != role:
                    continue
                if status and node.status != status:
                    continue
                results.append(node)
            return results

    async def count(
        self,
        *,
        role: Optional[NodeRole] = None,
        status: Optional[NodeStatus] = None,
    ) -> int:
        """Count nodes, optionally filtered."""
        nodes = await self.list_nodes(role=role, status=status)
        return len(nodes)

    async def get_leader(self) -> Optional[ClusterNode]:
        """Get the current leader node."""
        with self._lock:
            for node in self._nodes.values():
                if node.role == NodeRole.LEADER and node.is_available:
                    return node
            return None

    async def get_available_workers(self) -> List[ClusterNode]:
        """Get all available worker nodes."""
        return await self.list_nodes(role=NodeRole.WORKER, status=NodeStatus.ACTIVE)

    async def node_exists(self, node_id: str) -> bool:
        """Check if a node is registered."""
        with self._lock:
            return node_id in self._nodes

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_join(self, callback) -> None:
        self._on_join_callbacks.append(callback)

    def on_leave(self, callback) -> None:
        self._on_leave_callbacks.append(callback)

    def on_status_change(self, callback) -> None:
        self._on_status_change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_nodes": len(self._nodes),
                "max_nodes": self._max_nodes,
                "by_role": {
                    role.value: sum(1 for n in self._nodes.values() if n.role == role)
                    for role in NodeRole
                },
                "by_status": {
                    status.value: sum(1 for n in self._nodes.values() if n.status == status)
                    for status in NodeStatus
                },
            }
