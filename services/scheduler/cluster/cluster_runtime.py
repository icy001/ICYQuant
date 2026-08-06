"""Cluster Runtime — runtime execution context for a scheduler cluster node.

The :class:`ClusterRuntime` wraps a single scheduler node's runtime
context within the distributed cluster, bridging the scheduler engine
with cluster coordination.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .coordinator import ClusterCoordinator
from .distributed_queue import DistributedQueue
from .dispatcher import ClusterDispatcher

logger = logging.getLogger(__name__)


class ClusterRuntimePhase:
    """Phases within a cluster runtime lifecycle."""

    BOOTSTRAPPING = "bootstrapping"
    JOINING = "joining"
    SYNCING = "syncing"
    ACTIVE = "active"
    DRAINING = "draining"
    STANDBY = "standby"
    RECOVERING = "recovering"
    STOPPED = "stopped"


class ClusterRuntime:
    """Per-node cluster runtime context.

    Bridges the local scheduler engine with cluster-wide coordination
    services (coordinator, distributed queue, dispatcher).

    Usage::

        runtime = ClusterRuntime(node_id="scheduler-1")
        await runtime.initialize()
        await runtime.activate()
        # ... processing ...
        await runtime.deactivate()
    """

    def __init__(
        self,
        node_id: str,
        *,
        coordinator: Optional[ClusterCoordinator] = None,
        queue: Optional[DistributedQueue] = None,
        dispatcher: Optional[ClusterDispatcher] = None,
    ) -> None:
        self._node_id = node_id
        self._phase: str = ClusterRuntimePhase.BOOTSTRAPPING
        self._lock = threading.Lock()

        self._coordinator = coordinator or ClusterCoordinator(node_id=node_id)
        self._queue = queue or DistributedQueue()
        self._dispatcher = dispatcher or ClusterDispatcher(node_id=node_id)

        self._initialized_at: Optional[datetime] = None
        self._activated_at: Optional[datetime] = None
        self._shard_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def coordinator(self) -> ClusterCoordinator:
        return self._coordinator

    @property
    def queue(self) -> DistributedQueue:
        return self._queue

    @property
    def dispatcher(self) -> ClusterDispatcher:
        return self._dispatcher

    @property
    def is_active(self) -> bool:
        return self._phase == ClusterRuntimePhase.ACTIVE

    @property
    def is_leader(self) -> bool:
        return self._coordinator.is_leader

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize cluster runtime subsystems."""
        logger.info("Initializing cluster runtime [node=%s]", self._node_id)
        await self._coordinator.start()
        await self._queue.initialize()
        await self._dispatcher.initialize()
        self._initialized_at = datetime.now(timezone.utc)
        logger.info("Cluster runtime initialized [node=%s]", self._node_id)

    async def activate(self) -> None:
        """Activate the node for cluster work."""
        with self._lock:
            self._phase = ClusterRuntimePhase.ACTIVE
        self._activated_at = datetime.now(timezone.utc)
        logger.info("Cluster runtime activated [node=%s]", self._node_id)

    async def deactivate(self) -> None:
        """Deactivate the node, drain pending work."""
        with self._lock:
            self._phase = ClusterRuntimePhase.DRAINING

        logger.info("Deactivating cluster runtime [node=%s]", self._node_id)
        await self._dispatcher.drain()
        await self._queue.close()

        with self._lock:
            self._phase = ClusterRuntimePhase.STOPPED
        logger.info("Cluster runtime deactivated [node=%s]", self._node_id)

    async def recover(self) -> None:
        """Recover from a previous failure."""
        with self._lock:
            self._phase = ClusterRuntimePhase.RECOVERING

        logger.info("Recovering cluster runtime [node=%s]", self._node_id)
        await self._queue.recover()
        await self._dispatcher.recover()

        with self._lock:
            self._phase = ClusterRuntimePhase.ACTIVE
        logger.info("Cluster runtime recovered [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def enqueue(self, job: Any, *, priority: int = 0) -> str:
        """Enqueue a job into the distributed queue."""
        return await self._queue.enqueue(job, priority=priority)

    async def dequeue(self) -> Optional[Any]:
        """Dequeue the next job from the distributed queue."""
        return await self._queue.dequeue()

    async def dispatch(self, target: str, payload: Any) -> bool:
        """Dispatch a payload to a target node."""
        return await self._dispatcher.send(target=target, payload=payload)

    def get_runtime_info(self) -> Dict[str, Any]:
        """Return runtime information summary."""
        return {
            "node_id": self._node_id,
            "phase": self._phase,
            "is_leader": self.is_leader,
            "shard_count": self._shard_count,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "activated_at": self._activated_at.isoformat() if self._activated_at else None,
            "queue_depth": self._queue.depth if self._queue else 0,
        }
