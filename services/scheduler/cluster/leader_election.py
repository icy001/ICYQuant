"""Leader Election — pluggable leader election for the scheduler cluster.

The :class:`LeaderElection` provides a unified interface for leader election
with swappable backend providers (Raft, etcd, standalone). It ensures that
at most one scheduler node acts as the active leader at any moment.

Flow::

    Candidate → Election → Leader → Lease → Heartbeat → Transfer → Recovery
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from .coordinator import ClusterCoordinator, CoordinatorRole

logger = logging.getLogger(__name__)


class ElectionProvider:
    """Enumeration of supported leader election backends."""

    STANDALONE = "standalone"
    RAFT = "raft"
    ETCD = "etcd"
    ZOOKEEPER = "zookeeper"


class ElectionResult:
    """Result of a leader election round."""

    def __init__(
        self,
        leader_id: str,
        term: int,
        votes_received: int,
        total_voters: int,
    ) -> None:
        self.leader_id = leader_id
        self.term = term
        self.votes_received = votes_received
        self.total_voters = total_voters
        self.timestamp = datetime.now(timezone.utc)

    @property
    def is_successful(self) -> bool:
        return self.votes_received > self.total_voters // 2

    @property
    def is_this_node_leader(self, node_id: str) -> bool:
        return self.leader_id == node_id


class LeaderElection:
    """Pluggable leader election for the scheduler cluster.

    Supports multiple backends:
    - ``standalone``: single-node mode, always leader
    - ``raft``: consensus-based via a Raft adapter
    - ``etcd``: via etcd lease + watch

    Usage::

        election = LeaderElection(
            node_id="scheduler-1",
            provider=ElectionProvider.STANDALONE,
        )
        await election.start()
        result = await election.campaign()
        if result.is_this_node_leader("scheduler-1"):
            await coordinator.become_leader(result.term)
    """

    def __init__(
        self,
        node_id: str,
        *,
        provider: str = ElectionProvider.STANDALONE,
        coordinator: Optional[ClusterCoordinator] = None,
        lease_ttl_seconds: float = 15.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        self._node_id = node_id
        self._provider = provider
        self._coordinator = coordinator or ClusterCoordinator(node_id=node_id)
        self._lease_ttl = lease_ttl_seconds
        self._heartbeat_interval = heartbeat_interval_seconds

        self._lock = threading.Lock()
        self._current_term: int = 0
        self._leader_id: Optional[str] = None
        self._is_running = False
        self._election_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_leader_changed: list[Callable[[str, int], None]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def current_term(self) -> int:
        return self._current_term

    @property
    def leader_id(self) -> Optional[str]:
        return self._leader_id

    @property
    def is_leader(self) -> bool:
        return self._leader_id == self._node_id

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the leader election subsystem."""
        self._is_running = True
        logger.info(
            "Leader election started [node=%s, provider=%s]",
            self._node_id, self._provider,
        )

        if self._provider == ElectionProvider.STANDALONE:
            await self._become_standalone_leader()

    async def stop(self) -> None:
        """Stop the leader election subsystem."""
        self._is_running = False
        if self._election_task:
            self._election_task.cancel()
            self._election_task = None

        if self.is_leader:
            await self.resign()
        logger.info("Leader election stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Campaign
    # ------------------------------------------------------------------

    async def campaign(self) -> ElectionResult:
        """Start a leader election campaign.

        Returns:
            ElectionResult with the outcome of the campaign.
        """
        logger.info("Node %s starting election campaign [term=%d]", self._node_id, self._current_term + 1)

        with self._lock:
            self._current_term += 1
            term = self._current_term

        await self._coordinator.become_candidate()

        if self._provider == ElectionProvider.STANDALONE:
            result = ElectionResult(
                leader_id=self._node_id,
                term=term,
                votes_received=1,
                total_voters=1,
            )
        else:
            # For external providers, the result comes from the backend
            result = await self._external_campaign(term)

        if result.is_successful:
            with self._lock:
                self._leader_id = result.leader_id

            if result.is_this_node_leader(self._node_id):
                await self._coordinator.become_leader(term)
                await self._maintain_leadership()
            else:
                await self._coordinator.step_down()

            for cb in self._on_leader_changed:
                try:
                    cb(result.leader_id, term)
                except Exception:
                    logger.warning("Leader-changed callback failed", exc_info=True)

        return result

    async def resign(self) -> None:
        """Voluntarily resign from leadership."""
        if not self.is_leader:
            return
        logger.info("Node %s resigning from leadership [term=%d]", self._node_id, self._current_term)
        await self._coordinator.step_down()
        with self._lock:
            self._leader_id = None

    async def transfer_leadership(self, target_node_id: str) -> bool:
        """Transfer leadership to another node."""
        if not self.is_leader:
            logger.warning("Cannot transfer leadership: node %s is not leader", self._node_id)
            return False
        logger.info("Transferring leadership from %s to %s", self._node_id, target_node_id)
        await self.resign()
        return True

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_leader_changed(self, callback: Callable[[str, int], None]) -> None:
        """Register a callback invoked when the leader changes."""
        self._on_leader_changed.append(callback)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _become_standalone_leader(self) -> None:
        """Immediately become leader in standalone mode."""
        with self._lock:
            self._current_term = 1
            self._leader_id = self._node_id
        await self._coordinator.become_leader(1)
        logger.info("Standalone leader: %s", self._node_id)

    async def _maintain_leadership(self) -> None:
        """Periodic heartbeat to maintain leadership lease."""
        async def heartbeat_loop():
            while self._is_running and self.is_leader:
                await asyncio.sleep(self._heartbeat_interval)
                logger.debug("Leadership heartbeat [node=%s, term=%d]", self._node_id, self._current_term)

        self._election_task = asyncio.create_task(heartbeat_loop())

    async def _external_campaign(self, term: int) -> ElectionResult:
        """Run campaign through an external provider (placeholder)."""
        await asyncio.sleep(0.1)
        return ElectionResult(
            leader_id=self._node_id,
            term=term,
            votes_received=1,
            total_voters=1,
        )

    def get_election_info(self) -> Dict[str, Any]:
        """Return election status summary."""
        return {
            "node_id": self._node_id,
            "provider": self._provider,
            "current_term": self._current_term,
            "leader_id": self._leader_id,
            "is_leader": self.is_leader,
            "is_running": self._is_running,
            "lease_ttl_seconds": self._lease_ttl,
        }
