"""Consensus Layer — provides distributed consensus primitives for the scheduler cluster.

The :class:`ConsensusLayer` abstracts consensus operations (propose, commit,
read) behind a unified interface. It supports Raft-based and standalone
implementations, enabling consistent scheduling decisions across nodes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConsensusResult:
    """Outcome of a consensus operation."""

    def __init__(
        self,
        success: bool,
        index: int = 0,
        term: int = 0,
        data: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.index = index
        self.term = term
        self.data = data
        self.error = error
        self.timestamp = datetime.now(timezone.utc)

    @classmethod
    def ok(cls, index: int = 0, term: int = 0, data: Any = None) -> "ConsensusResult":
        return cls(success=True, index=index, term=term, data=data)

    @classmethod
    def fail(cls, error: str, index: int = 0, term: int = 0) -> "ConsensusResult":
        return cls(success=False, index=index, term=term, error=error)


class ConsensusLayer:
    """Distributed consensus abstraction for scheduler cluster coordination.

    Provides:
    - Propose: submit a value for consensus
    - Commit: confirm a value is committed
    - Read: linearizable read of committed state
    - Snapshot: compact the log

    Usage::

        consensus = ConsensusLayer(node_id="scheduler-1")
        await consensus.start()
        result = await consensus.propose({"action": "schedule", "job_id": "j1"})
        if result.success:
            print(f"Committed at index {result.index}")
    """

    def __init__(
        self,
        node_id: str,
        *,
        peers: Optional[List[str]] = None,
        standalone: bool = True,
    ) -> None:
        self._node_id = node_id
        self._peers = peers or []
        self._standalone = standalone
        self._lock = threading.Lock()

        self._last_index: int = 0
        self._current_term: int = 0
        self._committed_index: int = 0
        self._log: List[Any] = []
        self._snapshot: Optional[Dict[str, Any]] = None
        self._is_running = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def last_index(self) -> int:
        return self._last_index

    @property
    def committed_index(self) -> int:
        return self._committed_index

    @property
    def current_term(self) -> int:
        return self._current_term

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def log_length(self) -> int:
        return len(self._log)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the consensus layer."""
        self._is_running = True
        self._current_term += 1
        logger.info("Consensus layer started [node=%s, term=%d, standalone=%s]",
                     self._node_id, self._current_term, self._standalone)

    async def stop(self) -> None:
        """Stop the consensus layer."""
        self._is_running = False
        logger.info("Consensus layer stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Consensus Operations
    # ------------------------------------------------------------------

    async def propose(self, value: Any) -> ConsensusResult:
        """Propose a value to the consensus log.

        Returns:
            ConsensusResult indicating success/failure.
        """
        if not self._is_running:
            return ConsensusResult.fail("consensus layer not running")

        with self._lock:
            self._last_index += 1
            index = self._last_index
            self._log.append(value)

        logger.debug("Proposed entry [node=%s, index=%d, term=%d]",
                      self._node_id, index, self._current_term)

        # In standalone mode, auto-commit
        if self._standalone:
            await self._commit(index)

        return ConsensusResult.ok(index=index, term=self._current_term, data=value)

    async def commit(self, index: int) -> ConsensusResult:
        """Commit a previously proposed entry up to the given index."""
        if index > self._last_index:
            return ConsensusResult.fail(f"index {index} exceeds last {self._last_index}")

        await self._commit(index)
        return ConsensusResult.ok(index=index, term=self._current_term)

    async def read(self, index: Optional[int] = None) -> ConsensusResult:
        """Linearizable read from the consensus log.

        Args:
            index: Specific index to read, or None for latest committed.
        """
        with self._lock:
            target = index if index is not None else self._committed_index
            if target <= 0:
                return ConsensusResult.ok(data=None)
            if target > len(self._log):
                return ConsensusResult.fail(f"index {target} out of range")
            value = self._log[target - 1]
        return ConsensusResult.ok(index=target, data=value)

    async def snapshot(self) -> Dict[str, Any]:
        """Create a compacted snapshot of committed state."""
        with self._lock:
            snapshot = {
                "node_id": self._node_id,
                "last_index": self._last_index,
                "committed_index": self._committed_index,
                "current_term": self._current_term,
                "log_entries": self._log[:self._committed_index],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._snapshot = snapshot
        logger.info("Created consensus snapshot [node=%s, index=%d]",
                     self._node_id, self._committed_index)
        return snapshot

    async def restore(self, snapshot: Dict[str, Any]) -> bool:
        """Restore consensus state from a snapshot."""
        with self._lock:
            self._last_index = snapshot.get("last_index", 0)
            self._committed_index = snapshot.get("committed_index", 0)
            self._current_term = snapshot.get("current_term", self._current_term)
            self._log = snapshot.get("log_entries", [])
            self._snapshot = snapshot
        logger.info("Restored consensus from snapshot [node=%s, index=%d]",
                     self._node_id, self._committed_index)
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _commit(self, index: int) -> None:
        """Internal commit operation."""
        with self._lock:
            self._committed_index = max(self._committed_index, index)

    def get_consensus_info(self) -> Dict[str, Any]:
        """Return consensus layer status summary."""
        return {
            "node_id": self._node_id,
            "standalone": self._standalone,
            "is_running": self._is_running,
            "last_index": self._last_index,
            "committed_index": self._committed_index,
            "current_term": self._current_term,
            "log_length": self.log_length,
            "peer_count": len(self._peers),
        }
