"""Consensus Engine — abstraction over distributed consensus protocols.

Provides a unified interface for log replication, term management, and
commit-index tracking. This allows the workflow engine to remain agnostic
to the underlying consensus implementation (Raft, Paxos, etc.).

Key concepts:

* **Log Replication** — replicate state changes across cluster nodes
* **Term Management** — monotonically increasing term numbers for leader epochs
* **Commit Index** — the highest log entry known to be committed across the cluster
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .cluster_node import ClusterNode

logger = logging.getLogger(__name__)


class ConsensusBackend(str, Enum):
    """Supported consensus backends."""

    IN_MEMORY = "in_memory"
    RAFT = "raft"
    ETCD = "etcd"


@dataclass
class LogEntry:
    """A single entry in the consensus log."""

    index: int
    term: int
    command: str
    data: Dict[str, Any] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "term": self.term,
            "command": self.command,
            "data": dict(self.data),
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LogEntry:
        timestamp = data.get("timestamp")
        return cls(
            index=data["index"],
            term=data["term"],
            command=data["command"],
            data=dict(data.get("data", {})),
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
        )


class ConsensusEngine:
    """Abstraction layer for distributed consensus.

    Usage::

        consensus = ConsensusEngine(node=...)
        await consensus.start()
        await consensus.propose(command="update_state", data={...})
        committed = await consensus.get_committed_entries(since=0)
    """

    def __init__(
        self,
        *,
        node: ClusterNode,
        backend: ConsensusBackend = ConsensusBackend.IN_MEMORY,
    ) -> None:
        self._node = node
        self._backend = backend
        self._lock = threading.RLock()

        # Consensus state
        self._current_term = 0
        self._commit_index = 0
        self._last_applied = 0
        self._log: List[LogEntry] = []

        # Runtime
        self._started = False
        self._proposal_queue: asyncio.Queue = asyncio.Queue()
        self._apply_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_term(self) -> int:
        with self._lock:
            return self._current_term

    @property
    def commit_index(self) -> int:
        with self._lock:
            return self._commit_index

    @property
    def log_length(self) -> int:
        with self._lock:
            return len(self._log)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the consensus engine."""
        logger.info("ConsensusEngine: starting for node %s (backend=%s)", self._node.node_id, self._backend.value)
        self._started = True
        self._apply_task = asyncio.create_task(self._apply_loop())

    async def stop(self) -> None:
        """Stop the consensus engine."""
        logger.info("ConsensusEngine: stopping for node %s", self._node.node_id)
        self._started = False
        if self._apply_task:
            self._apply_task.cancel()
            try:
                await self._apply_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Term management
    # ------------------------------------------------------------------

    def increment_term(self) -> int:
        """Increment the current term (called when starting a new election)."""
        with self._lock:
            self._current_term += 1
            logger.debug("ConsensusEngine: term incremented to %d", self._current_term)
            return self._current_term

    def update_term(self, term: int) -> bool:
        """Update current term from a peer (higher term wins)."""
        with self._lock:
            if term > self._current_term:
                self._current_term = term
                return True
            return False

    # ------------------------------------------------------------------
    # Log operations
    # ------------------------------------------------------------------

    async def propose(self, command: str, data: Dict[str, Any]) -> int:
        """Propose a new log entry to the cluster.

        Returns the index of the proposed entry.
        """
        if not self._started:
            raise RuntimeError("ConsensusEngine not started")

        with self._lock:
            self._current_term += 1
            index = len(self._log) + 1
            entry = LogEntry(
                index=index,
                term=self._current_term,
                command=command,
                data=data,
            )
            self._log.append(entry)
            logger.debug("ConsensusEngine: proposed entry %d (command=%s)", index, command)

        await self._proposal_queue.put(entry)
        return index

    async def get_entry(self, index: int) -> Optional[LogEntry]:
        """Retrieve a log entry by index."""
        with self._lock:
            if 1 <= index <= len(self._log):
                return self._log[index - 1]
            return None

    async def get_entries(self, since: int = 0, limit: int = 100) -> List[LogEntry]:
        """Retrieve log entries since a given index."""
        with self._lock:
            start = max(0, since)
            end = min(len(self._log), start + limit)
            return list(self._log[start:end])

    async def get_committed_entries(self, since: int = 0) -> List[LogEntry]:
        """Retrieve committed entries since a given index."""
        with self._lock:
            end = min(self._commit_index, len(self._log))
            start = max(0, since)
            return [e for e in self._log[start:end] if e.index <= self._commit_index]

    # ------------------------------------------------------------------
    # Commit management
    # ------------------------------------------------------------------

    def update_commit_index(self, index: int) -> None:
        """Advance the commit index (called when a majority has replicated)."""
        with self._lock:
            if index > self._commit_index:
                self._commit_index = min(index, len(self._log))
                logger.debug("ConsensusEngine: commit index advanced to %d", self._commit_index)

    # ------------------------------------------------------------------
    # Apply loop
    # ------------------------------------------------------------------

    async def _apply_loop(self) -> None:
        """Background loop that applies committed entries to the state machine."""
        while self._started:
            try:
                entry = await asyncio.wait_for(self._proposal_queue.get(), timeout=1.0)
                # In production, this would wait for replication quorum
                await self._apply_entry(entry)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ConsensusEngine: error in apply loop")

    async def _apply_entry(self, entry: LogEntry) -> None:
        """Apply a single log entry to the state machine."""
        logger.debug("ConsensusEngine: applying entry %d (command=%s)", entry.index, entry.command)
        self._last_applied = entry.index
        self.update_commit_index(entry.index)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": self._backend.value,
                "current_term": self._current_term,
                "commit_index": self._commit_index,
                "last_applied": self._last_applied,
                "log_length": len(self._log),
            }
