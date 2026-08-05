"""Cluster platform for ICYQuant service discovery.

Provides ``ClusterPlatform`` for node join/leave, snapshot
sync, topology sync, and reserved leader election.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class ClusterNode:
    """Represents a node in the cluster."""

    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        role: str = "worker",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.role = role
        self.metadata = metadata or {}
        self.joined_at = datetime.utcnow()
        self.last_heartbeat = time.monotonic()
        self.healthy = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role,
            "metadata": dict(self.metadata),
            "joined_at": self.joined_at.isoformat(),
            "healthy": self.healthy,
            "uptime_s": time.monotonic() - self.last_heartbeat,
        }

    def __repr__(self) -> str:
        return (
            f"ClusterNode(id={self.node_id}, host={self.host}:{self.port}, "
            f"role={self.role}, healthy={self.healthy})"
        )


class ClusterPlatform:
    """Cluster management for service discovery.

    Supports node join, leave, snapshot sync, topology sync,
    and reserved leader election.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        node_id: Optional[str] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._node_id = node_id or f"node-{id(self)}"
        self._nodes: Dict[str, ClusterNode] = {}
        self._self_node: Optional[ClusterNode] = None
        self._leader_id: Optional[str] = None
        self._join_callbacks: List[Callable] = []
        self._leave_callbacks: List[Callable] = []
        self._join_count = 0
        self._leave_count = 0
        self._sync_count = 0

    def set_self_node(
        self,
        host: str,
        port: int,
        role: str = "worker",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClusterNode:
        """Set the local node's identity.

        Args:
            host: Hostname or IP.
            port: Port number.
            role: Node role.
            metadata: Optional metadata.

        Returns:
            The local ClusterNode.
        """
        with self._lock:
            self._self_node = ClusterNode(
                self._node_id,
                host,
                port,
                role,
                metadata,
            )
            self._nodes[self._node_id] = self._self_node
            self._context.register("cluster", self)
        logger.info(
            "Local node set: %s:%d (role=%s).", host, port, role
        )
        return self._self_node

    async def join(
        self,
        host: str,
        port: int,
        role: str = "worker",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Join a node to the cluster.

        Args:
            host: Node host.
            port: Node port.
            role: Node role.
            metadata: Optional metadata.

        Returns:
            Join result.
        """
        with self._lock:
            self._join_count += 1
            node_id = f"node-{len(self._nodes) + 1}"

        node = ClusterNode(node_id, host, port, role, metadata)
        with self._lock:
            self._nodes[node_id] = node

        for cb in self._join_callbacks:
            try:
                coro = cb(node)
                if asyncio.iscoroutine(coro):
                    await coro
            except Exception as exc:
                logger.warning(
                    "Join callback failed for %s: %s",
                    node_id,
                    exc,
                )

        logger.info(
            "Node joined cluster: %s (%s:%d).",
            node_id,
            host,
            port,
        )
        return {
            "success": True,
            "node_id": node_id,
            "node": node.to_dict(),
        }

    async def leave(
        self, node_id: str
    ) -> Dict[str, Any]:
        """Remove a node from the cluster.

        Args:
            node_id: Node to remove.

        Returns:
            Leave result.
        """
        with self._lock:
            self._leave_count += 1
            if node_id not in self._nodes:
                return {
                    "success": False,
                    "error": f"Node {node_id} not found",
                }
            node = self._nodes.pop(node_id)

        for cb in self._leave_callbacks:
            try:
                coro = cb(node)
                if asyncio.iscoroutine(coro):
                    await coro
            except Exception as exc:
                logger.warning(
                    "Leave callback failed for %s: %s",
                    node_id,
                    exc,
                )

        logger.info("Node left cluster: %s.", node_id)
        return {
            "success": True,
            "node_id": node_id,
        }

    def list_nodes(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [n.to_dict() for n in self._nodes.values()]

    def get_node(self, node_id: str) -> Optional[ClusterNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def get_leader(self) -> Optional[str]:
        with self._lock:
            return self._leader_id

    def set_leader(self, node_id: str) -> None:
        with self._lock:
            self._leader_id = node_id
        logger.info("Leader elected: %s.", node_id)

    def on_join(self, callback: Callable) -> None:
        with self._lock:
            self._join_callbacks.append(callback)

    def on_leave(self, callback: Callable) -> None:
        with self._lock:
            self._leave_callbacks.append(callback)

    def mark_node_healthy(self, node_id: str) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.healthy = True
                node.last_heartbeat = time.monotonic()

    def mark_node_unhealthy(self, node_id: str) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.healthy = False

    def get_node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    def get_healthy_count(self) -> int:
        with self._lock:
            return sum(
                1 for n in self._nodes.values() if n.healthy
            )

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "node_id": self._node_id,
                "self_node": (
                    self._self_node.to_dict()
                    if self._self_node
                    else None
                ),
                "total_nodes": len(self._nodes),
                "healthy_nodes": self.get_healthy_count(),
                "leader_id": self._leader_id,
                "join_count": self._join_count,
                "leave_count": self._leave_count,
                "sync_count": self._sync_count,
                "join_callbacks": len(self._join_callbacks),
                "leave_callbacks": len(self._leave_callbacks),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ClusterPlatform(id={self._node_id}, "
                f"nodes={len(self._nodes)}, "
                f"leader={self._leader_id})"
            )
