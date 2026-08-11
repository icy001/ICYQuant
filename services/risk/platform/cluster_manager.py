"""
Cluster Manager — Manage risk cluster topology and node lifecycle.

Handles node registration, discovery, health monitoring,
and topology management for the distributed risk cluster.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ClusterTopology(str, Enum):
    """Risk cluster topology type."""
    SINGLE_NODE = "single_node"
    ACTIVE_PASSIVE = "active_passive"
    ACTIVE_ACTIVE = "active_active"
    GEO_DISTRIBUTED = "geo_distributed"


class ClusterState(str, Enum):
    """Overall cluster health state."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PARTITIONED = "partitioned"
    FAILED = "failed"


@dataclass
class NodeInfo:
    """Detailed node information."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    host: str = "localhost"
    port: int = 9090
    region: str = "default"
    zone: str = "default"
    status: str = "active"
    is_leader: bool = False
    version: str = "0.4.0"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    capacity: float = 1.0
    current_load: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterConfig:
    """Cluster configuration."""
    topology: ClusterTopology = ClusterTopology.ACTIVE_PASSIVE
    min_nodes: int = 1
    max_nodes: int = 10
    heartbeat_interval_seconds: float = 5.0
    heartbeat_timeout_seconds: float = 15.0
    rebalance_enabled: bool = True
    auto_failover: bool = True
    quorum_size: int = 2


class ClusterManager:
    """
    Risk cluster topology and node lifecycle manager.

    Handles node registration, health monitoring, discovery,
    and topology management for the distributed risk cluster.

    Usage::

        manager = ClusterManager(config=ClusterConfig())
        await manager.initialize()
        await manager.register_node(NodeInfo(host="192.168.1.10"))
        nodes = await manager.get_healthy_nodes()
    """

    def __init__(
        self,
        config: Optional[ClusterConfig] = None,
        platform: Any = None,
    ) -> None:
        self._config = config or ClusterConfig()
        self._platform = platform
        self._nodes: dict[str, NodeInfo] = {}
        self._state = ClusterState.HEALTHY
        self._lock = asyncio.Lock()
        self._initialized = False
        self._running = False

        # Register self
        self_node = NodeInfo(is_leader=True)
        self._nodes[self_node.node_id] = self_node

    async def initialize(self) -> None:
        """Initialize the cluster manager."""
        self._initialized = True
        self._running = True
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._health_monitor_loop())
        logger.info(f"ClusterManager initialized (topology: {self._config.topology.value}).")

    async def stop(self) -> None:
        """Stop the cluster manager."""
        self._running = False
        logger.info("ClusterManager stopped.")

    # ---- Node Management ----

    async def register_node(self, node: NodeInfo) -> bool:
        """Register a new node in the cluster."""
        async with self._lock:
            if len(self._nodes) >= self._config.max_nodes:
                logger.warning(f"Max nodes ({self._config.max_nodes}) reached")
                return False
            self._nodes[node.node_id] = node
            logger.info(f"Node registered: {node.node_id} ({node.host}:{node.port})")
            return True

    async def deregister_node(self, node_id: str) -> bool:
        """Remove a node from the cluster."""
        async with self._lock:
            if len(self._nodes) <= self._config.min_nodes:
                return False
            removed = self._nodes.pop(node_id, None)
            if removed:
                logger.info(f"Node deregistered: {node_id}")
            return removed is not None

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get node info by ID."""
        return self._nodes.get(node_id)

    async def get_nodes(self) -> dict[str, NodeInfo]:
        """Get all cluster nodes."""
        return dict(self._nodes)

    async def get_healthy_nodes(self) -> list[NodeInfo]:
        """Get all healthy nodes."""
        now = datetime.now(timezone.utc)
        return [
            n for n in self._nodes.values()
            if n.status == "active"
            and (now - n.last_seen).total_seconds() < self._config.heartbeat_timeout_seconds
        ]

    async def get_leader(self) -> Optional[NodeInfo]:
        """Get the current leader node."""
        for node in self._nodes.values():
            if node.is_leader and node.status == "active":
                return node
        return None

    async def promote_leader(self, node_id: str) -> bool:
        """Promote a node to be the new leader."""
        async with self._lock:
            # Demote current leader
            for node in self._nodes.values():
                node.is_leader = False
            # Promote new leader
            node = self._nodes.get(node_id)
            if node:
                node.is_leader = True
                logger.info(f"Leader promoted: {node_id}")
                return True
            return False

    # ---- Heartbeat ----

    async def heartbeat(self, node_id: str) -> bool:
        """Process heartbeat from a node."""
        node = self._nodes.get(node_id)
        if node:
            node.last_seen = datetime.now(timezone.utc)
            node.status = "active"
            return True
        return False

    # ---- Discovery ----

    async def discover_nodes(self) -> list[NodeInfo]:
        """Discover all nodes in the cluster."""
        return list(self._nodes.values())

    # ---- Health ----

    async def get_cluster_state(self) -> ClusterState:
        """Get current cluster state."""
        return self._state

    async def get_cluster_summary(self) -> dict[str, Any]:
        """Get cluster health summary."""
        healthy = await self.get_healthy_nodes()
        leader = await self.get_leader()
        return {
            "state": self._state.value,
            "topology": self._config.topology.value,
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(healthy),
            "leader_node": leader.node_id if leader else None,
            "auto_failover": self._config.auto_failover,
        }

    # ---- Internal Loops ----

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat monitoring loop."""
        while self._running:
            await asyncio.sleep(self._config.heartbeat_interval_seconds)
            # Check for stale nodes
            now = datetime.now(timezone.utc)
            async with self._lock:
                for node_id, node in list(self._nodes.items()):
                    if (now - node.last_seen).total_seconds() > self._config.heartbeat_timeout_seconds:
                        node.status = "unhealthy"
                        logger.warning(f"Node {node_id} marked unhealthy (stale heartbeat)")

    async def _health_monitor_loop(self) -> None:
        """Periodic cluster health monitoring."""
        while self._running:
            await asyncio.sleep(10.0)
            healthy = await self.get_healthy_nodes()
            if len(healthy) == 0:
                self._state = ClusterState.FAILED
            elif len(healthy) < len(self._nodes):
                self._state = ClusterState.DEGRADED
            else:
                self._state = ClusterState.HEALTHY

    async def health_check(self) -> dict[str, Any]:
        """Check cluster manager health."""
        return await self.get_cluster_summary()
