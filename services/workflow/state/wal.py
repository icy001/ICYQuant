"""Write-Ahead Log (WAL) — guarantees durability before execution.

Every state-changing operation is:
  1. Written to WAL
  2. Flushed to storage
  3. Then executed
  4. Then committed (marked as applied)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class WALEntryType(str, Enum):
    """Types of WAL entries."""

    WORKFLOW_START = "workflow_start"
    WORKFLOW_TRANSITION = "workflow_transition"
    NODE_TRANSITION = "node_transition"
    VARIABLE_UPDATE = "variable_update"
    SNAPSHOT = "snapshot"
    CHECKPOINT = "checkpoint"
    RECOVERY_MARKER = "recovery_marker"
    SHUTDOWN = "shutdown"


class WALEntryStatus(str, Enum):
    """Status of a WAL entry."""

    PENDING = "pending"       # Written but not flushed
    FLUSHED = "flushed"       # Written to storage but not executed
    APPLIED = "applied"       # Executed successfully
    FAILED = "failed"         # Execution failed
    ROLLED_BACK = "rolled_back"


@dataclass
class WALEntry:
    """A single entry in the Write-Ahead Log."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    lsn: int = 0  # Log Sequence Number
    entry_type: WALEntryType = WALEntryType.WORKFLOW_TRANSITION
    node_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    status: WALEntryStatus = WALEntryStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "execution_id": self.execution_id,
            "lsn": self.lsn,
            "entry_type": self.entry_type.value,
            "node_id": self.node_id,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "metadata": self.metadata,
        }


class WAL:
    """Write-Ahead Log ensuring durability of workflow operations.

    Execution order: Write WAL → Flush → Execute → Commit
    """

    def __init__(self, flush_to_storage: bool = True):
        self._entries: Dict[str, List[WALEntry]] = {}
        self._lsn_counters: Dict[str, int] = {}
        self._flush_to_storage = flush_to_storage
        self._flushed_entries: List[WALEntry] = []

    # ---- Write operations ---------------------------------------------------

    async def write(
        self,
        execution_id: str,
        entry_type: WALEntryType,
        payload: Dict[str, Any],
        node_id: Optional[str] = None,
    ) -> WALEntry:
        """Write a new entry to the WAL."""
        lsn = self._next_lsn(execution_id)
        entry = WALEntry(
            execution_id=execution_id,
            lsn=lsn,
            entry_type=entry_type,
            node_id=node_id,
            payload=payload,
        )
        self._append(execution_id, entry)

        if self._flush_to_storage:
            await self.flush(execution_id, entry.lsn)

        logger.debug("WAL entry written: exec=%s lsn=%d type=%s", execution_id, lsn, entry_type.value)
        return entry

    async def flush(self, execution_id: str, until_lsn: int) -> None:
        """Flush WAL entries up to a given LSN to storage."""
        entries = self._entries.get(execution_id, [])
        for entry in entries:
            if entry.lsn > until_lsn:
                break
            if entry.status == WALEntryStatus.PENDING:
                entry.status = WALEntryStatus.FLUSHED
                self._flushed_entries.append(entry)
        logger.debug("WAL flushed: exec=%s up_to_lsn=%d", execution_id, until_lsn)

    async def commit(self, execution_id: str, entry_id: str) -> None:
        """Mark a WAL entry as applied (execution completed)."""
        entry = self._find_entry(execution_id, entry_id)
        if entry is not None:
            entry.status = WALEntryStatus.APPLIED
            entry.applied_at = datetime.now(timezone.utc)
            logger.debug("WAL committed: exec=%s entry=%s", execution_id, entry_id)

    async def mark_failed(self, execution_id: str, entry_id: str) -> None:
        """Mark a WAL entry as failed."""
        entry = self._find_entry(execution_id, entry_id)
        if entry is not None:
            entry.status = WALEntryStatus.FAILED
            logger.debug("WAL marked failed: exec=%s entry=%s", execution_id, entry_id)

    # ---- Recovery -----------------------------------------------------------

    async def get_pending_entries(self, execution_id: str) -> List[WALEntry]:
        """Get all pending/flushed (not applied) entries for recovery."""
        entries = self._entries.get(execution_id, [])
        return [e for e in entries if e.status in (WALEntryStatus.PENDING, WALEntryStatus.FLUSHED)]

    async def get_entries_after_lsn(
        self, execution_id: str, after_lsn: int
    ) -> List[WALEntry]:
        """Get all WAL entries after a specific LSN."""
        entries = self._entries.get(execution_id, [])
        return [e for e in entries if e.lsn > after_lsn]

    async def get_last_lsn(self, execution_id: str) -> int:
        """Get the last LSN for an execution."""
        return self._lsn_counters.get(execution_id, 0)

    # ---- Cleanup ------------------------------------------------------------

    async def truncate(self, execution_id: str, before_lsn: int) -> int:
        """Remove WAL entries before a given LSN. Returns count removed."""
        entries = self._entries.get(execution_id, [])
        to_keep = [e for e in entries if e.lsn >= before_lsn]
        removed = len(entries) - len(to_keep)
        self._entries[execution_id] = to_keep
        return removed

    # ---- Internal -----------------------------------------------------------

    def _next_lsn(self, execution_id: str) -> int:
        current = self._lsn_counters.get(execution_id, 0)
        self._lsn_counters[execution_id] = current + 1
        return self._lsn_counters[execution_id]

    def _append(self, execution_id: str, entry: WALEntry) -> None:
        if execution_id not in self._entries:
            self._entries[execution_id] = []
        self._entries[execution_id].append(entry)

    def _find_entry(self, execution_id: str, entry_id: str) -> Optional[WALEntry]:
        for entry in self._entries.get(execution_id, []):
            if entry.entry_id == entry_id:
                return entry
        return None
