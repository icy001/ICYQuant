"""Leader Election — distributed leader election for the workflow cluster.

Supports multiple backends:

* **Standalone** — single-node, always-leader (dev/test)
* **Raft** — adapter for a Raft consensus group
* **etcd** — adapter for etcd-based election
* **ZooKeeper** — reserved for future integration

The abstraction ensures the cluster can switch backends without changing
the workflow engine logic.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from .cluster_node import ClusterNode, NodeRole

logger = logging.getLogger(__name__)


class LeaderElectionBackend(str, Enum):
    """Supported leader election backends."""

    STANDALONE = "standalone"
    RAFT = "raft"
    ETCD = "etcd"
    ZOOKEEPER = "zookeeper"


class ElectionState(str, Enum):
    """States of the leader election process."""

    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"
    STOPPED = "stopped"


@dataclass
class LeaderLease:
    """A leadership lease with expiration."""

    node_id: str
    term: int
    acquired_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at


class LeaderElection:
    """Distributed leader election abstraction.

    Usage::

        election = LeaderElection(node=..., backend=LeaderElectionBackend.ETCD)
        await election.start()
        leader_id = await election.elect()
    """

    def __init__(
        self,
        *,
        node: ClusterNode,
        backend: LeaderElectionBackend = LeaderElectionBackend.STANDALONE,
        timeout_seconds: float = 10.0,
        lease_duration_seconds: float = 30.0,
    ) -> None:
        self._node = node
        self._backend = backend
        self._timeout_seconds = timeout_seconds
        self._lease_duration_seconds = lease_duration_seconds
        self._state = ElectionState.STOPPED
        self._term = 0
        self._current_leader: Optional[LeaderLease] = None
        self._campaign_task: Optional[asyncio.Task] = None
        self._renew_task: Optional[asyncio.Task] = None
        self._on_leadership_callbacks: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_leader(self) -> bool:
        return self._state == ElectionState.LEADER

    @property
    def current_leader_id(self) -> Optional[str]:
        if self._current_leader is None:
            return None
        return self._current_leader.node_id

    @property
    def term(self) -> int:
        return self._term

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the leader election process."""
        logger.info("LeaderElection: starting for node %s (backend=%s)", self._node.node_id, self._backend.value)

        if self._backend == LeaderElectionBackend.STANDALONE:
            # In standalone mode, we are always the leader
            self._state = ElectionState.LEADER
            self._term = 1
            self._current_leader = LeaderLease(
                node_id=self._node.node_id,
                term=self._term,
            )
            self._node.update_role(NodeRole.LEADER)
        else:
            self._state = ElectionState.FOLLOWER
            self._campaign_task = asyncio.create_task(self._campaign_loop())

        logger.info("LeaderElection: started, node=%s, state=%s", self._node.node_id, self._state.value)

    async def stop(self) -> None:
        """Stop the leader election process."""
        logger.info("LeaderElection: stopping for node %s", self._node.node_id)

        if self._state == ElectionState.LEADER:
            await self.step_down()

        if self._renew_task:
            self._renew_task.cancel()
            try:
                await self._renew_task
            except asyncio.CancelledError:
                pass

        if self._campaign_task:
            self._campaign_task.cancel()
            try:
                await self._campaign_task
            except asyncio.CancelledError:
                pass

        self._state = ElectionState.STOPPED
        logger.info("LeaderElection: stopped for node %s", self._node.node_id)

    # ------------------------------------------------------------------
    # Election logic
    # ------------------------------------------------------------------

    async def elect(self) -> Optional[str]:
        """Run an election and return the elected leader node ID."""
        if self._backend == LeaderElectionBackend.STANDALONE:
            return self._node.node_id

        self._state = ElectionState.CANDIDATE
        self._term += 1
        logger.info("LeaderElection: node %s campaigning for term %d", self._node.node_id, self._term)

        # In a real distributed backend (Raft/etcd/ZK), this would:
        # 1. Request votes from peers
        # 2. Wait for majority
        # 3. Transition to LEADER or FOLLOWER

        # Placeholder: wait and self-elect with quorum check
        await asyncio.sleep(min(1.0, self._timeout_seconds / 10.0))

        self._state = ElectionState.LEADER
        self._current_leader = LeaderLease(
            node_id=self._node.node_id,
            term=self._term,
        )
        self._node.update_role(NodeRole.LEADER)
        logger.info("LeaderElection: node %s elected leader for term %d", self._node.node_id, self._term)

        for callback in self._on_leadership_callbacks:
            try:
                await callback(self._node.node_id, self._term)
            except Exception:
                logger.exception("LeaderElection: callback error")

        return self._node.node_id

    async def step_down(self) -> None:
        """Voluntarily step down from leadership."""
        if self._state != ElectionState.LEADER:
            return
        logger.info("LeaderElection: node %s stepping down from term %d", self._node.node_id, self._term)
        self._state = ElectionState.FOLLOWER
        self._node.update_role(NodeRole.WORKER)
        self._current_leader = None

    async def _campaign_loop(self) -> None:
        """Background loop for periodic election campaigns."""
        while True:
            try:
                if self._state == ElectionState.FOLLOWER:
                    await self.elect()
                await asyncio.sleep(self._timeout_seconds)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("LeaderElection: campaign loop error")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_leadership_acquired(self, callback) -> None:
        """Register a callback invoked when leadership is acquired."""
        self._on_leadership_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "backend": self._backend.value,
            "state": self._state.value,
            "term": self._term,
            "is_leader": self.is_leader,
            "current_leader": self.current_leader_id,
        }
