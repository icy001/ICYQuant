"""Queue Replication — replicates queue state for durability and failover.

The :class:`QueueReplication` ensures queue entries survive node failures
by replicating them across multiple nodes. Supports synchronous and
asynchronous replication modes, plus batch replication for throughput.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ReplicationMode:
    """Queue replication modes."""

    SYNC = "sync"
    ASYNC = "async"
    BATCH = "batch"


class QueueReplication:
    """Replicates queue entries across cluster nodes for durability.

    Modes:
    - sync: ack only after all replicas confirm
    - async: fire-and-forget replication
    - batch: accumulate and send in batches

    Usage::

        repl = QueueReplication(mode=ReplicationMode.ASYNC)
        await repl.start()
        await repl.replicate(entry_id="e1", payload=job)
        status = repl.get_replication_status("e1")
    """

    def __init__(
        self,
        *,
        mode: str = ReplicationMode.ASYNC,
        replication_factor: int = 2,
        batch_size: int = 100,
        batch_interval_seconds: float = 0.5,
    ) -> None:
        self._mode = mode
        self._replication_factor = replication_factor
        self._batch_size = batch_size
        self._batch_interval = batch_interval_seconds
        self._lock = threading.Lock()

        self._is_running = False
        self._replicas: Dict[str, Set[str]] = {}  # entry_id → set of node_ids that have a replica
        self._batch_buffer: List[tuple] = []  # (entry_id, payload)
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def replication_factor(self) -> int:
        return self._replication_factor

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._batch_buffer)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the replication subsystem."""
        self._is_running = True
        if self._mode == ReplicationMode.BATCH:
            self._task = asyncio.create_task(self._batch_flush_loop())
        logger.info("Queue replication started [mode=%s, factor=%d]", self._mode, self._replication_factor)

    async def stop(self) -> None:
        """Stop replication and flush pending batches."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._mode == ReplicationMode.BATCH:
            await self._flush_batch()
        logger.info("Queue replication stopped")

    # ------------------------------------------------------------------
    # Replication
    # ------------------------------------------------------------------

    async def replicate(
        self,
        entry_id: str,
        payload: Any,
        *,
        target_nodes: Optional[List[str]] = None,
    ) -> bool:
        """Replicate a queue entry to target nodes.

        Args:
            entry_id: The queue entry ID.
            payload: The entry payload.
            target_nodes: Specific nodes to replicate to. If None, auto-select.

        Returns:
            True if replicated to at least replication_factor nodes.
        """
        if not self._is_running:
            return False

        if self._mode == ReplicationMode.BATCH:
            with self._lock:
                self._batch_buffer.append((entry_id, payload))
                if len(self._batch_buffer) >= self._batch_size:
                    asyncio.create_task(self._flush_batch())
            return True

        # Sync or async single replication
        replica_nodes = target_nodes or self._select_replica_nodes()
        success_count = 0

        for node_id in replica_nodes:
            try:
                await self._send_replica(node_id, entry_id, payload)
                success_count += 1
            except Exception:
                logger.warning("Replication to %s failed for entry %s", node_id, entry_id)

        with self._lock:
            self._replicas.setdefault(entry_id, set()).update(replica_nodes[:success_count])

        return success_count >= self._replication_factor

    def get_replication_status(self, entry_id: str) -> Dict[str, Any]:
        """Get the replication status for a queue entry."""
        with self._lock:
            replicas = self._replicas.get(entry_id, set())
        return {
            "entry_id": entry_id,
            "replica_count": len(replicas),
            "replication_factor": self._replication_factor,
            "is_fully_replicated": len(replicas) >= self._replication_factor,
            "replica_nodes": list(replicas),
        }

    async def remove_replica(self, entry_id: str) -> None:
        """Remove replicas for a completed/acknowledged entry."""
        with self._lock:
            self._replicas.pop(entry_id, None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _select_replica_nodes(self) -> List[str]:
        """Select nodes for replication (placeholder)."""
        return [f"node-{i}" for i in range(self._replication_factor)]

    async def _send_replica(self, node_id: str, entry_id: str, payload: Any) -> None:
        """Send a replica to a specific node (placeholder)."""
        logger.debug("Sending replica of %s to %s", entry_id, node_id)
        await asyncio.sleep(0)  # simulate async I/O

    async def _flush_batch(self) -> None:
        """Flush the batch buffer."""
        with self._lock:
            batch = list(self._batch_buffer)
            self._batch_buffer.clear()

        if batch:
            logger.debug("Flushing replication batch [size=%d]", len(batch))
            for entry_id, payload in batch:
                try:
                    await self._send_replica("batch-node", entry_id, payload)
                except Exception:
                    logger.warning("Batch replication failed for entry %s", entry_id)

    async def _batch_flush_loop(self) -> None:
        """Periodic batch flush loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self._batch_interval)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Batch flush loop error", exc_info=True)

    def get_replication_info(self) -> Dict[str, Any]:
        """Return replication status summary."""
        with self._lock:
            return {
                "mode": self._mode,
                "replication_factor": self._replication_factor,
                "is_running": self._is_running,
                "total_entries": len(self._replicas),
                "pending_batch": len(self._batch_buffer),
            }
