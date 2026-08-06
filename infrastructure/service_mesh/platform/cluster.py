"""Mesh Cluster Manager for the Service Mesh Platform.

Provides ``MeshClusterManager`` for multi-node cluster operations
including node join/leave, leader sync, policy sync, and snapshot sync.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class NodeState(str, Enum):
    """State of a cluster node."""

    JOINING = "joining"
    ACTIVE = "active"
    LEAVING = "leaving"
    INACTIVE = "inactive"
    FAILED = "failed"


class ClusterNode:
    """Represents a node in the mesh cluster."""

    def __init__(
        self,
        node_id: str,
        host: str = "localhost",
        port: int = 8080,
        is_leader: bool = False,
    ) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.is_leader = is_leader
        self.state = NodeState.JOINING
        self.version = "0.4.0"
        self.metadata: Dict[str, Any] = {}
        self.capabilities: List[str] = []
        self.joined_at = datetime.utcnow()
        self.last_heartbeat: Optional[datetime] = None

    def activate(self) -> None:
        self.state = NodeState.ACTIVE
        self.last_heartbeat = datetime.utcnow()

    def deactivate(self) -> None:
        self.state = NodeState.INACTIVE

    def leave(self) -> None:
        self.state = NodeState.LEAVING

    def fail(self) -> None:
        self.state = NodeState.FAILED

    def heartbeat(self) -> None:
        self.last_heartbeat = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "is_leader": self.is_leader,
            "state": self.state.value,
            "version": self.version,
            "metadata": self.metadata,
            "capabilities": self.capabilities,
            "joined_at": self.joined_at.isoformat(),
            "last_heartbeat": (
                self.last_heartbeat.isoformat()
                if self.last_heartbeat
                else None
            ),
        }


class MeshClusterManager:
    """Manages mesh cluster nodes and synchronization."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._nodes: Dict[str, ClusterNode] = {}
        self._leader_id: Optional[str] = None
        self._self_node_id: Optional[str] = None
        self._sync_handlers: Dict[str, Callable] = {}
        self._elected = False
        self._next_id = 0
        self._max_nodes = 50

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"node-{int(time.monotonic())}-{self._next_id}"

    def register_sync_handler(
        self,
        sync_type: str,
        handler: Callable,
    ) -> None:
        self._sync_handlers[sync_type] = handler

    async def join_cluster(
        self,
        node_id: Optional[str] = None,
        host: str = "localhost",
        port: int = 8080,
        capabilities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Join a node to the cluster."""
        nid = node_id or self._generate_id()
        node = ClusterNode(nid, host, port)
        node.capabilities = capabilities or []

        with self._lock:
            self._nodes[nid] = node

        # Auto-elect first node as leader
        if len(self._nodes) == 1:
            node.is_leader = True
            self._leader_id = nid
            self._elected = True

        node.activate()
        self._self_node_id = nid

        self._telemetry.log_platform_event(
            "node_joined", "cluster",
            {"node_id": nid, "host": host, "port": port},
        )

        logger.info(
            "Node '%s' joined cluster (%s:%d).",
            nid,
            host,
            port,
        )
        return node.to_dict()

    async def leave_cluster(
        self, node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove a node from the cluster."""
        nid = node_id or self._self_node_id
        if nid is None:
            return {"success": False, "error": "No node to leave"}

        node = self._nodes.get(nid)
        if node is None:
            return {"success": False, "error": "Node not found"}

        node.leave()

        with self._lock:
            self._nodes.pop(nid, None)
            if self._leader_id == nid:
                self._leader_id = None
                self._elected = False

        self._telemetry.log_platform_event(
            "node_left", "cluster",
            {"node_id": nid},
        )

        logger.info("Node '%s' left cluster.", nid)
        return {"success": True, "node_id": nid}

    async def elect_leader(self) -> Dict[str, Any]:
        """Elect a leader from active nodes."""
        active_nodes = [
            n for n in self._nodes.values()
            if n.state == NodeState.ACTIVE
        ]
        if not active_nodes:
            return {
                "success": False,
                "error": "No active nodes for election",
            }

        # Simple election: first active node becomes leader
        leader = active_nodes[0]
        for n in self._nodes.values():
            n.is_leader = (n.node_id == leader.node_id)

        self._leader_id = leader.node_id
        self._elected = True

        self._telemetry.log_platform_event(
            "leader_elected", "cluster",
            {"leader_id": leader.node_id},
        )
        logger.info(
            "Node '%s' elected as leader.", leader.node_id
        )
        return {
            "success": True,
            "leader_id": leader.node_id,
        }

    async def sync_policies(
        self, policies: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synchronize policies across cluster."""
        handler = self._sync_handlers.get("policies")
        if handler:
            try:
                result = handler(policies)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:
                return {
                    "success": False,
                    "error": str(exc),
                }

        self._telemetry.log_platform_event(
            "policies_synced", "cluster",
            {"node_count": len(self._nodes)},
        )
        return {
            "success": True,
            "synced_nodes": len(self._nodes),
        }

    async def sync_snapshot(
        self, snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synchronize a snapshot across cluster."""
        handler = self._sync_handlers.get("snapshot")
        if handler:
            try:
                result = handler(snapshot_data)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:
                return {
                    "success": False,
                    "error": str(exc),
                }

        self._telemetry.log_platform_event(
            "snapshot_synced", "cluster",
            {"node_count": len(self._nodes)},
        )
        return {
            "success": True,
            "synced_nodes": len(self._nodes),
        }

    def get_node(self, node_id: str) -> Optional[ClusterNode]:
        return self._nodes.get(node_id)

    def get_leader(self) -> Optional[ClusterNode]:
        if self._leader_id:
            return self._nodes.get(self._leader_id)
        return None

    def list_nodes(
        self, state: Optional[NodeState] = None
    ) -> List[Dict[str, Any]]:
        nodes = list(self._nodes.values())
        if state:
            nodes = [n for n in nodes if n.state == state]
        return [n.to_dict() for n in nodes]

    def get_cluster_topology(self) -> Dict[str, Any]:
        nodes = list(self._nodes.values())
        active = [
            n for n in nodes
            if n.state == NodeState.ACTIVE
        ]
        return {
            "total_nodes": len(nodes),
            "active_nodes": len(active),
            "leader_id": self._leader_id,
            "self_node_id": self._self_node_id,
            "nodes": [n.to_dict() for n in nodes],
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_nodes": len(self._nodes),
                "active_nodes": sum(
                    1
                    for n in self._nodes.values()
                    if n.state == NodeState.ACTIVE
                ),
                "leader_id": self._leader_id,
                "self_node_id": self._self_node_id,
                "elected": self._elected,
                "by_state": self._count_by_state(),
            }

    def _count_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for n in self._nodes.values():
            state = n.state.value
            counts[state] = counts.get(state, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshClusterManager(nodes={len(self._nodes)}, "
                f"leader={self._leader_id})"
            )
