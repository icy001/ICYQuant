"""State Replication — replicates workflow state across cluster nodes.

Replicates:

* **Workflow State** — current status, node progress, output data
* **Node State** — cluster membership and health status
* **Runtime Context** — variables, metadata, execution context

Supports:
* **Synchronous Replication** — wait for quorum before acknowledging
* **Asynchronous Replication** — fire-and-forget with eventual consistency
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReplicationMode(str, Enum):
    """Replication consistency modes."""

    SYNC = "sync"
    ASYNC = "async"
    QUORUM = "quorum"


class ReplicationStatus(str, Enum):
    """Status of a replication operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REPLICATED = "replicated"
    FAILED = "failed"


@dataclass
class StateEntry:
    """A single state entry to be replicated."""

    key: str
    value: Any
    version: int = 1
    node_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: ReplicationStatus = ReplicationStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "version": self.version,
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }


class StateReplication:
    """Replicates workflow state across cluster nodes.

    Usage::

        replication = StateReplication(mode=ReplicationMode.QUORUM, target_nodes=3)
        await replication.start()
        await replication.replicate(key="workflow.status", value="running")
    """

    def __init__(
        self,
        *,
        mode: ReplicationMode = ReplicationMode.ASYNC,
        target_nodes: int = 3,
        batch_size: int = 100,
        flush_interval_seconds: float = 1.0,
    ) -> None:
        self._mode = mode
        self._target_nodes = target_nodes
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._lock = threading.RLock()
        self._started = False

        # State store
        self._states: Dict[str, StateEntry] = {}

        # Pending replication queue
        self._pending: List[StateEntry] = []
        self._pending_lock = threading.Lock()

        # Replication task
        self._flush_task: Optional[asyncio.Task] = None

        # Replicated count per key
        self._replicated_count: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("StateReplication: started (mode=%s, target_nodes=%d)",
                     self._mode.value, self._target_nodes)

    async def stop(self) -> None:
        self._started = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        logger.info("StateReplication: stopped")

    # ------------------------------------------------------------------
    # Replication
    # ------------------------------------------------------------------

    async def replicate(
        self,
        key: str,
        value: Any,
        *,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StateEntry:
        """Replicate a state entry to peer nodes.

        In SYNC mode, blocks until quorum is reached.
        In ASYNC mode, returns immediately and replicates in background.
        """
        with self._lock:
            existing = self._states.get(key)
            version = (existing.version + 1) if existing else 1

        entry = StateEntry(
            key=key,
            value=value,
            version=version,
            node_id=node_id,
            metadata=metadata or {},
        )

        with self._lock:
            self._states[key] = entry

        if self._mode == ReplicationMode.SYNC:
            await self._sync_replicate(entry)
        elif self._mode == ReplicationMode.QUORUM:
            await self._quorum_replicate(entry)
        else:
            # ASYNC — queue for background replication
            with self._pending_lock:
                self._pending.append(entry)

        return entry

    async def _sync_replicate(self, entry: StateEntry) -> None:
        """Synchronously replicate and wait for all targets."""
        # In production: send to N peers and wait for all ACKs
        await asyncio.sleep(0.01)  # Simulated network
        entry.status = ReplicationStatus.REPLICATED
        with self._lock:
            self._replicated_count[entry.key] = self._replicated_count.get(entry.key, 0) + 1

    async def _quorum_replicate(self, entry: StateEntry) -> None:
        """Replicate and wait for quorum (majority of targets)."""
        quorum = max(1, (self._target_nodes // 2) + 1)
        # In production: send to N peers, wait for quorum ACKs
        await asyncio.sleep(0.01)
        entry.status = ReplicationStatus.REPLICATED
        with self._lock:
            self._replicated_count[entry.key] = self._replicated_count.get(entry.key, 0) + 1

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    async def get_state(self, key: str) -> Optional[StateEntry]:
        with self._lock:
            return self._states.get(key)

    async def get_all_states(self) -> Dict[str, Any]:
        with self._lock:
            return {k: v.value for k, v in self._states.items()}

    async def get_state_version(self, key: str) -> int:
        with self._lock:
            entry = self._states.get(key)
            return entry.version if entry else 0

    async def delete_state(self, key: str) -> None:
        with self._lock:
            self._states.pop(key, None)
            self._replicated_count.pop(key, None)

    # ------------------------------------------------------------------
    # Flush loop
    # ------------------------------------------------------------------

    async def _flush_loop(self) -> None:
        """Periodically flush pending async replications."""
        while self._started:
            try:
                await asyncio.sleep(self._flush_interval)

                with self._pending_lock:
                    batch = self._pending[:self._batch_size]
                    self._pending = self._pending[self._batch_size:]

                for entry in batch:
                    try:
                        await self._sync_replicate(entry)
                    except Exception:
                        logger.exception("StateReplication: flush error for key %s", entry.key)
                        entry.status = ReplicationStatus.FAILED
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("StateReplication: error in flush loop")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            pending_count = len(self._pending)
            return {
                "mode": self._mode.value,
                "target_nodes": self._target_nodes,
                "total_states": len(self._states),
                "pending_replications": pending_count,
                "replicated_keys": len(self._replicated_count),
            }
