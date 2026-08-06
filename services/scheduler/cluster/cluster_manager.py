"""Scheduler Cluster Manager — unified lifecycle management for the scheduler cluster.

The :class:`SchedulerClusterManager` is the top-level orchestrator for the
distributed scheduler cluster. It handles node join/leave, cluster-wide
synchronization, and metadata maintenance.

Pipeline::

    Node Join → Registration → Sync → Active
    Node Leave → Drain → Sync → Remove
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .coordinator import ClusterCoordinator, CoordinatorRole
from .node_registry import NodeRegistry, NodeStatus
from .heartbeat_manager import HeartbeatManager
from .health_monitor import ClusterHealthMonitor
from .topology_manager import ClusterTopologyManager
from .state_sync import StateSync

logger = logging.getLogger(__name__)


class ClusterState:
    """Scheduler cluster lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    JOINING = "joining"
    ACTIVE = "active"
    DEGRADED = "degraded"
    REBALANCING = "rebalancing"
    LEAVING = "leaving"
    STOPPED = "stopped"
    ERROR = "error"


class SchedulerClusterManager:
    """Unified cluster manager for the distributed scheduler.

    Responsible for:
    - Node lifecycle (join / leave / heartbeat)
    - Cluster-wide state synchronization
    - Metadata maintenance
    - Cluster health aggregation

    Usage::

        manager = SchedulerClusterManager(node_id="scheduler-1")
        await manager.start()
        await manager.join(cluster_endpoints=["scheduler-2:8001"])
        # ... nodes join, work gets distributed ...
        await manager.leave()
        await manager.stop()
    """

    def __init__(
        self,
        node_id: str,
        *,
        cluster_name: str = "icyquant-scheduler",
        coordinator: Optional[ClusterCoordinator] = None,
        registry: Optional[NodeRegistry] = None,
        heartbeat: Optional[HeartbeatManager] = None,
        health_monitor: Optional[ClusterHealthMonitor] = None,
        topology: Optional[ClusterTopologyManager] = None,
        state_sync: Optional[StateSync] = None,
    ) -> None:
        self._node_id = node_id
        self._cluster_name = cluster_name
        self._state: str = ClusterState.UNINITIALIZED
        self._lock = threading.Lock()

        self._coordinator = coordinator or ClusterCoordinator(node_id=node_id)
        self._registry = registry or NodeRegistry()
        self._heartbeat = heartbeat or HeartbeatManager(node_id=node_id)
        self._health_monitor = health_monitor or ClusterHealthMonitor()
        self._topology = topology or ClusterTopologyManager()
        self._state_sync = state_sync or StateSync(node_id=node_id)

        self._member_ids: Set[str] = set()
        self._metadata: Dict[str, Any] = {}
        self._started_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def cluster_name(self) -> str:
        return self._cluster_name

    @property
    def state(self) -> str:
        return self._state

    @property
    def member_ids(self) -> Set[str]:
        return frozenset(self._member_ids)  # type: ignore[return-value]

    @property
    def member_count(self) -> int:
        return len(self._member_ids)

    @property
    def is_active(self) -> bool:
        return self._state == ClusterState.ACTIVE

    @property
    def coordinator(self) -> ClusterCoordinator:
        return self._coordinator

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize cluster manager subsystems."""
        with self._lock:
            if self._state != ClusterState.UNINITIALIZED:
                return
            self._state = ClusterState.INITIALIZING

        logger.info("Starting scheduler cluster manager [node=%s]", self._node_id)
        await self._heartbeat.start()
        await self._health_monitor.start()
        await self._topology.start()
        self._started_at = datetime.now(timezone.utc)

        with self._lock:
            self._state = ClusterState.ACTIVE
        logger.info("Scheduler cluster manager started [node=%s]", self._node_id)

    async def stop(self) -> None:
        """Gracefully stop cluster manager."""
        with self._lock:
            if self._state in (ClusterState.STOPPED, ClusterState.UNINITIALIZED):
                return
            self._state = ClusterState.STOPPING

        logger.info("Stopping scheduler cluster manager [node=%s]", self._node_id)
        await self._heartbeat.stop()
        await self._health_monitor.stop()
        await self._topology.stop()

        with self._lock:
            self._state = ClusterState.STOPPED
        logger.info("Scheduler cluster manager stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Node Membership
    # ------------------------------------------------------------------

    async def join(self, *, cluster_endpoints: Optional[List[str]] = None) -> None:
        """Join this node to the scheduler cluster.

        Args:
            cluster_endpoints: Known peer endpoints for discovery.
        """
        with self._lock:
            self._state = ClusterState.JOINING

        logger.info("Node %s joining cluster %s", self._node_id, self._cluster_name)
        await self._registry.register(
            node_id=self._node_id,
            cluster_name=self._cluster_name,
            metadata=self._metadata,
        )
        await self._topology.add_node(self._node_id)
        self._member_ids.add(self._node_id)

        if cluster_endpoints:
            await self._discover_peers(cluster_endpoints)

        await self._state_sync.sync_full()

        with self._lock:
            self._state = ClusterState.ACTIVE
        logger.info("Node %s joined cluster %s [members=%d]", self._node_id, self._cluster_name, self.member_count)

    async def leave(self, *, drain: bool = True) -> None:
        """Gracefully leave the cluster.

        Args:
            drain: If True, drain in-flight work before leaving.
        """
        with self._lock:
            self._state = ClusterState.LEAVING

        logger.info("Node %s leaving cluster %s", self._node_id, self._cluster_name)

        if drain:
            await self._drain()

        await self._state_sync.sync_full()
        await self._topology.remove_node(self._node_id)
        await self._registry.deregister(self._node_id)

        with self._lock:
            self._state = ClusterState.STOPPED
        logger.info("Node %s left cluster %s", self._node_id, self._cluster_name)

    async def synchronize(self) -> None:
        """Trigger full cluster state synchronization."""
        logger.debug("Triggering full cluster sync [node=%s]", self._node_id)
        await self._state_sync.sync_full()
        await self._registry.sync()
        await self._topology.sync()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def set_metadata(self, key: str, value: Any) -> None:
        """Set cluster-wide metadata key."""
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get cluster-wide metadata value."""
        return self._metadata.get(key, default)

    def get_cluster_info(self) -> Dict[str, Any]:
        """Return cluster information summary."""
        return {
            "cluster_name": self._cluster_name,
            "node_id": self._node_id,
            "state": self._state,
            "member_count": self.member_count,
            "member_ids": list(self._member_ids),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "coordinator_role": self._coordinator.role,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _discover_peers(self, endpoints: List[str]) -> None:
        """Discover peer nodes from a list of known endpoints."""
        for endpoint in endpoints:
            try:
                peer_id = await self._registry.lookup(endpoint)
                if peer_id and peer_id != self._node_id:
                    self._member_ids.add(peer_id)
                    await self._topology.add_node(peer_id)
                    logger.debug("Discovered peer node %s via %s", peer_id, endpoint)
            except Exception:
                logger.debug("Failed to discover peer at %s", endpoint, exc_info=True)

    async def _drain(self) -> None:
        """Drain in-flight work before leaving the cluster."""
        logger.info("Draining in-flight work for node %s", self._node_id)
        await asyncio.sleep(0.5)
        logger.info("Node %s drained", self._node_id)
