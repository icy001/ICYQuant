"""Workflow Cluster Manager — unified entry point for distributed workflow cluster.

The :class:`WorkflowClusterManager` is responsible for:

* Cluster membership lifecycle (join / leave / synchronize)
* Node discovery and health monitoring
* Coordination of leader election, consensus, and failover
* Recovery orchestration across the cluster

Architecture::

    WorkflowClusterManager
           │
    ClusterCoordinator
           │
    ┌──────┼──────┐
    Leader  Worker A  Worker B
    └──────┼──────┘
    DistributedScheduler
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .cluster_node import ClusterNode, NodeRole, NodeStatus
from .coordinator import ClusterCoordinator
from .node_registry import NodeRegistry
from .heartbeat import HeartbeatMonitor
from .synchronization import ClusterSynchronizer

logger = logging.getLogger(__name__)


class ClusterState(str, Enum):
    """Lifecycle states of the workflow cluster."""

    UNINITIALIZED = "uninitialized"
    JOINING = "joining"
    ACTIVE = "active"
    DEGRADED = "degraded"
    LEAVING = "leaving"
    LEFT = "left"
    ERROR = "error"


@dataclass
class ClusterConfig:
    """Configuration for the workflow cluster."""

    cluster_id: str = "default"
    heartbeat_interval_seconds: float = 5.0
    heartbeat_timeout_seconds: float = 15.0
    lease_duration_seconds: float = 30.0
    leader_election_timeout_seconds: float = 10.0
    sync_interval_seconds: float = 10.0
    max_nodes: int = 100
    quorum_size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowClusterManager:
    """Unified cluster manager for the distributed workflow execution system.

    Usage::

        cluster = WorkflowClusterManager(config=ClusterConfig())
        await cluster.join()
        await cluster.synchronize()
        await cluster.leave()
    """

    def __init__(self, *, config: Optional[ClusterConfig] = None) -> None:
        self._config = config or ClusterConfig()
        self._state = ClusterState.UNINITIALIZED
        self._lock = threading.RLock()
        self._joined_at: Optional[datetime] = None
        self._node_id = str(uuid.uuid4())

        # Sub-systems — initialised during join()
        self._coordinator: Optional[ClusterCoordinator] = None
        self._node_registry: Optional[NodeRegistry] = None
        self._heartbeat_monitor: Optional[HeartbeatMonitor] = None
        self._synchronizer: Optional[ClusterSynchronizer] = None

        # Local state
        self._local_node: Optional[ClusterNode] = None
        self._peer_nodes: Dict[str, ClusterNode] = {}
        self._join_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def state(self) -> ClusterState:
        with self._lock:
            return self._state

    @property
    def is_leader(self) -> bool:
        if self._local_node is None:
            return False
        return self._local_node.role == NodeRole.LEADER

    @property
    def peer_count(self) -> int:
        with self._lock:
            return len(self._peer_nodes)

    @property
    def local_node(self) -> Optional[ClusterNode]:
        return self._local_node

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def join(
        self,
        *,
        host: str = "localhost",
        port: int = 9090,
        role: NodeRole = NodeRole.WORKER,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Join the workflow cluster.

        Parameters
        ----------
        host: Advertised host for this node.
        port: Advertised port for this node.
        role: Initial node role.
        metadata: Optional node metadata (capabilities, tags, etc.).
        """
        with self._lock:
            if self._state in (ClusterState.ACTIVE, ClusterState.DEGRADED):
                logger.warning("Node %s is already in the cluster", self._node_id)
                return
            self._state = ClusterState.JOINING

        logger.info("ClusterManager: node %s joining cluster %s", self._node_id, self._config.cluster_id)

        # Initialise local node
        self._local_node = ClusterNode(
            node_id=self._node_id,
            host=host,
            port=port,
            role=role,
            status=NodeStatus.JOINING,
            metadata=metadata or {},
        )

        # Initialise sub-systems
        self._node_registry = NodeRegistry(max_nodes=self._config.max_nodes)
        self._heartbeat_monitor = HeartbeatMonitor(
            interval_seconds=self._config.heartbeat_interval_seconds,
            timeout_seconds=self._config.heartbeat_timeout_seconds,
        )
        self._synchronizer = ClusterSynchronizer(interval_seconds=self._config.sync_interval_seconds)
        self._coordinator = ClusterCoordinator(
            node=self._local_node,
            registry=self._node_registry,
            heartbeat=self._heartbeat_monitor,
            config=self._config,
        )

        # Start sub-systems
        await self._node_registry.start()
        await self._heartbeat_monitor.start()
        await self._synchronizer.start()
        await self._coordinator.start()

        # Register self
        await self._node_registry.register(self._local_node)

        with self._lock:
            self._state = ClusterState.ACTIVE
            self._joined_at = datetime.utcnow()

        self._join_event.set()
        logger.info("ClusterManager: node %s joined cluster %s", self._node_id, self._config.cluster_id)

    async def leave(self, *, graceful: bool = True) -> None:
        """Leave the workflow cluster.

        Parameters
        ----------
        graceful: If True, drain tasks before leaving.
        """
        with self._lock:
            if self._state in (ClusterState.LEFT, ClusterState.UNINITIALIZED):
                return
            self._state = ClusterState.LEAVING

        logger.info("ClusterManager: node %s leaving cluster %s", self._node_id, self._config.cluster_id)

        if self._local_node:
            self._local_node.update_status(NodeStatus.LEAVING)

        if self._coordinator:
            await self._coordinator.stop(graceful=graceful)
        if self._synchronizer:
            await self._synchronizer.stop()
        if self._heartbeat_monitor:
            await self._heartbeat_monitor.stop()
        if self._node_registry:
            if self._local_node:
                await self._node_registry.deregister(self._node_id)
            await self._node_registry.stop()

        self._peer_nodes.clear()

        with self._lock:
            self._state = ClusterState.LEFT
        logger.info("ClusterManager: node %s left cluster %s", self._node_id, self._config.cluster_id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize cluster state with peers."""
        if not self._synchronizer:
            raise RuntimeError("Cluster not joined")
        return await self._synchronizer.sync()

    # ------------------------------------------------------------------
    # Cluster membership
    # ------------------------------------------------------------------

    async def register_peer(self, node: ClusterNode) -> None:
        """Register a discovered peer node."""
        if not self._node_registry:
            raise RuntimeError("Cluster not joined")
        with self._lock:
            self._peer_nodes[node.node_id] = node
        await self._node_registry.register(node)

    async def deregister_peer(self, node_id: str) -> None:
        """Remove a peer node from the cluster."""
        if self._node_registry:
            await self._node_registry.deregister(node_id)
        with self._lock:
            self._peer_nodes.pop(node_id, None)

    async def get_node(self, node_id: str) -> Optional[ClusterNode]:
        """Retrieve a node by ID."""
        if not self._node_registry:
            return None
        return await self._node_registry.get(node_id)

    async def list_nodes(
        self,
        *,
        role: Optional[NodeRole] = None,
        status: Optional[NodeStatus] = None,
    ) -> List[ClusterNode]:
        """List cluster nodes, optionally filtered."""
        if not self._node_registry:
            return []
        return await self._node_registry.list_nodes(role=role, status=status)

    async def node_count(self) -> int:
        """Return the total number of nodes in the cluster."""
        if not self._node_registry:
            return 0
        return await self._node_registry.count()

    # ------------------------------------------------------------------
    # Health & Diagnostics
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        """Return a health report for the cluster."""
        report: Dict[str, Any] = {
            "cluster_id": self._config.cluster_id,
            "node_id": self._node_id,
            "state": self._state.value,
            "is_leader": self.is_leader,
            "joined_at": self._joined_at.isoformat() if self._joined_at else None,
            "peer_count": self.peer_count,
            "subsystems": {},
        }
        if self._coordinator:
            report["subsystems"]["coordinator"] = self._coordinator.health_report()
        if self._heartbeat_monitor:
            report["subsystems"]["heartbeat"] = self._heartbeat_monitor.health_report()
        if self._node_registry:
            report["subsystems"]["registry"] = self._node_registry.health_report()
        return report
