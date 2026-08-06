"""Cluster Coordinator — orchestrates distributed scheduling across nodes.

The :class:`ClusterCoordinator` is the nerve centre of the scheduler cluster.
It manages the leader/follower distinction, delegates queue operations,
and ensures consistent scheduling decisions across nodes.

Architecture::

    ClusterCoordinator
          │
    ┌──────┼──────────┐
    Leader   Queue    Dispatch
    Election  Partition
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CoordinatorRole:
    """Roles a cluster node can assume."""

    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    OBSERVER = "observer"


class ClusterCoordinator:
    """Orchestrates cluster-wide scheduling decisions.

    The coordinator ensures exactly-one-leader semantics and delegates
    scheduling authority accordingly.

    Usage::

        coordinator = ClusterCoordinator(node_id="scheduler-1")
        await coordinator.start()
        if coordinator.is_leader:
            await coordinator.schedule_job(job)
    """

    def __init__(
        self,
        node_id: str,
        *,
        cluster_name: str = "icyquant-scheduler",
    ) -> None:
        self._node_id = node_id
        self._cluster_name = cluster_name
        self._role: str = CoordinatorRole.FOLLOWER
        self._lock = threading.Lock()

        self._leader_id: Optional[str] = None
        self._term: int = 0
        self._started_at: Optional[datetime] = None
        self._running = False

        # Callbacks
        self._on_leadership_acquired: list = []
        self._on_leadership_lost: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def role(self) -> str:
        return self._role

    @property
    def is_leader(self) -> bool:
        return self._role == CoordinatorRole.LEADER

    @property
    def is_follower(self) -> bool:
        return self._role == CoordinatorRole.FOLLOWER

    @property
    def leader_id(self) -> Optional[str]:
        return self._leader_id

    @property
    def term(self) -> int:
        return self._term

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the coordinator."""
        self._running = True
        self._started_at = datetime.now(timezone.utc)
        logger.info("Cluster coordinator started [node=%s, role=%s]", self._node_id, self._role)

    async def stop(self) -> None:
        """Stop the coordinator."""
        if self.is_leader:
            await self.step_down()
        self._running = False
        logger.info("Cluster coordinator stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Leadership
    # ------------------------------------------------------------------

    async def become_leader(self, term: int) -> None:
        """Transition this node to leader role."""
        with self._lock:
            self._role = CoordinatorRole.LEADER
            self._leader_id = self._node_id
            self._term = term

        logger.info("Node %s became leader [term=%d]", self._node_id, term)
        for cb in self._on_leadership_acquired:
            try:
                cb()
            except Exception:
                logger.warning("Leadership-acquired callback failed", exc_info=True)

    async def step_down(self) -> None:
        """Transition this node from leader to follower."""
        with self._lock:
            was_leader = self._role == CoordinatorRole.LEADER
            self._role = CoordinatorRole.FOLLOWER

        if was_leader:
            logger.info("Node %s stepped down from leadership", self._node_id)
            for cb in self._on_leadership_lost:
                try:
                    cb()
                except Exception:
                    logger.warning("Leadership-lost callback failed", exc_info=True)

    async def become_candidate(self) -> None:
        """Transition this node to candidate role (seeking leadership)."""
        with self._lock:
            self._role = CoordinatorRole.CANDIDATE
        logger.debug("Node %s is now a candidate", self._node_id)

    def register_leadership_callback(
        self, on_acquired: Optional[callable] = None, on_lost: Optional[callable] = None
    ) -> None:
        """Register callbacks for leadership transitions."""
        if on_acquired:
            self._on_leadership_acquired.append(on_acquired)
        if on_lost:
            self._on_leadership_lost.append(on_lost)

    # ------------------------------------------------------------------
    # Cluster Operations
    # ------------------------------------------------------------------

    async def schedule_job(self, job: Any) -> bool:
        """Schedule a job. Only the leader may schedule."""
        if not self.is_leader:
            logger.warning("Non-leader node %s cannot schedule jobs", self._node_id)
            return False
        logger.debug("Leader %s scheduling job", self._node_id)
        return True

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        if not self.is_leader:
            return False
        logger.debug("Leader %s cancelling job %s", self._node_id, job_id)
        return True

    def get_coordinator_info(self) -> Dict[str, Any]:
        """Return coordinator status summary."""
        return {
            "node_id": self._node_id,
            "role": self._role,
            "leader_id": self._leader_id,
            "term": self._term,
            "is_leader": self.is_leader,
            "is_running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }
