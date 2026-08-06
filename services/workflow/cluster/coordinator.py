"""Cluster Coordinator — orchestrates leader election, heartbeat monitoring, and failover.

The :class:`ClusterCoordinator` is the central coordination layer that:

* Manages the leader election process
* Monitors node heartbeats and detects failures
* Coordinates failover when a node becomes unreachable
* Maintains cluster-wide consensus for critical decisions
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .cluster_node import ClusterNode, NodeRole, NodeStatus
from .cluster_manager import ClusterConfig
from .node_registry import NodeRegistry
from .heartbeat import HeartbeatMonitor
from .leader_election import LeaderElection, LeaderElectionBackend
from .consensus import ConsensusEngine
from .quorum import QuorumManager

logger = logging.getLogger(__name__)


class CoordinatorState:
    """Internal state of the cluster coordinator."""

    STOPPED = "stopped"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"


class ClusterCoordinator:
    """Central coordinator for the distributed workflow cluster.

    Usage::

        coordinator = ClusterCoordinator(node=..., registry=..., heartbeat=...)
        await coordinator.start()
        # cluster operates ...
        await coordinator.stop()
    """

    def __init__(
        self,
        *,
        node: ClusterNode,
        registry: NodeRegistry,
        heartbeat: HeartbeatMonitor,
        config: ClusterConfig,
    ) -> None:
        self._node = node
        self._registry = registry
        self._heartbeat = heartbeat
        self._config = config
        self._state = CoordinatorState.STOPPED
        self._lock = threading.RLock()
        self._started_at: Optional[datetime] = None

        # Sub-systems
        self._leader_election: Optional[LeaderElection] = None
        self._consensus: Optional[ConsensusEngine] = None
        self._quorum: Optional[QuorumManager] = None

        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._failover_callbacks: List = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def is_leader(self) -> bool:
        if self._leader_election is None:
            return False
        return self._leader_election.is_leader

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the coordinator and all sub-systems."""
        with self._lock:
            if self._state == CoordinatorState.ACTIVE:
                return
            self._state = CoordinatorState.STARTING
            self._started_at = datetime.utcnow()

        logger.info("Coordinator: starting for node %s", self._node.node_id)

        # Initialise sub-systems
        self._leader_election = LeaderElection(
            node=self._node,
            backend=LeaderElectionBackend.STANDALONE,
            timeout_seconds=self._config.leader_election_timeout_seconds,
        )
        self._consensus = ConsensusEngine(node=self._node)
        self._quorum = QuorumManager(
            min_nodes=3,
            quorum_size=self._config.quorum_size,
        )

        await self._leader_election.start()
        await self._consensus.start()
        await self._quorum.start()

        # Start failure monitor
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        with self._lock:
            self._state = CoordinatorState.ACTIVE
        logger.info("Coordinator: started for node %s", self._node.node_id)

    async def stop(self, *, graceful: bool = True) -> None:
        """Stop the coordinator."""
        with self._lock:
            if self._state == CoordinatorState.STOPPED:
                return
            self._state = CoordinatorState.STOPPING

        logger.info("Coordinator: stopping for node %s", self._node.node_id)

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._quorum:
            await self._quorum.stop()
        if self._consensus:
            await self._consensus.stop()
        if self._leader_election:
            await self._leader_election.stop()

        with self._lock:
            self._state = CoordinatorState.STOPPED
        logger.info("Coordinator: stopped for node %s", self._node.node_id)

    # ------------------------------------------------------------------
    # Failure monitor
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Background loop that monitors nodes and triggers failover."""
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)

                nodes = await self._registry.list_nodes()
                now = datetime.utcnow()

                for node in nodes:
                    if node.node_id == self._node.node_id:
                        continue
                    if node.last_heartbeat is None:
                        continue

                    elapsed = (now - node.last_heartbeat).total_seconds()
                    if elapsed > self._config.heartbeat_timeout_seconds * 2:
                        # Node is unreachable
                        logger.warning("Coordinator: node %s is unreachable (%.1fs since last heartbeat)",
                                       node.node_id, elapsed)
                        node.mark_unreachable()
                        await self._registry.update(node)
                        await self._trigger_failover(node.node_id)
                    elif elapsed > self._config.heartbeat_timeout_seconds:
                        # Node is suspect
                        if node.status != NodeStatus.SUSPECT:
                            logger.warning("Coordinator: node %s is suspect", node.node_id)
                            node.update_status(NodeStatus.SUSPECT)
                            await self._registry.update(node)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Coordinator: error in monitor loop")

    async def _trigger_failover(self, failed_node_id: str) -> None:
        """Trigger failover for a failed node."""
        logger.info("Coordinator: triggering failover for node %s", failed_node_id)
        for callback in self._failover_callbacks:
            try:
                await callback(failed_node_id)
            except Exception:
                logger.exception("Coordinator: failover callback error for node %s", failed_node_id)

    def on_failover(self, callback) -> None:
        """Register a callback invoked when a node failure is detected."""
        self._failover_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Leader election delegation
    # ------------------------------------------------------------------

    async def elect_leader(self) -> Optional[str]:
        """Run leader election and return the elected node ID."""
        if not self._leader_election:
            raise RuntimeError("Coordinator not started")
        return await self._leader_election.elect()

    async def step_down(self) -> None:
        """Voluntarily step down from leadership."""
        if self._leader_election:
            await self._leader_election.step_down()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "state": self._state,
            "is_leader": self.is_leader,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "subsystems": {},
        }
        if self._leader_election:
            report["subsystems"]["leader_election"] = self._leader_election.health_report()
        if self._consensus:
            report["subsystems"]["consensus"] = self._consensus.health_report()
        if self._quorum:
            report["subsystems"]["quorum"] = self._quorum.health_report()
        return report
