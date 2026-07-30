"""ICYQuant Transaction Log.

Write-ahead transaction log for ACID operations in the lakehouse.
Ensures atomicity and durability of data writes.

Supports:
    - Write-ahead logging (WAL)
    - Crash recovery
    - Log compaction
    - Sequence number tracking
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LogEntryType(str, Enum):
    """Types of transaction log entries."""

    BEGIN = "begin"
    COMMIT = "commit"
    ABORT = "abort"
    ADD_FILE = "add_file"
    REMOVE_FILE = "remove_file"
    UPDATE_METADATA = "update_metadata"
    CREATE_SNAPSHOT = "create_snapshot"
    CHECKPOINT = "checkpoint"


@dataclass
class LogEntry:
    """A single entry in the transaction log."""

    entry_id: str
    sequence_number: int
    entry_type: LogEntryType
    transaction_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "sequence_number": self.sequence_number,
            "entry_type": self.entry_type.value,
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LogEntry":
        return cls(
            entry_id=d["entry_id"],
            sequence_number=d["sequence_number"],
            entry_type=LogEntryType(d["entry_type"]),
            transaction_id=d["transaction_id"],
            timestamp=datetime.fromisoformat(d["timestamp"]) if "timestamp" in d else datetime.utcnow(),
            data=d.get("data", {}),
            checksum=d.get("checksum", ""),
        )


@dataclass
class CheckpointInfo:
    """Checkpoint metadata."""

    sequence_number: int
    timestamp: datetime
    snapshot_id: str = ""
    file_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TransactionLog:
    """Write-Ahead Transaction Log.

    Provides ACID guarantees for lakehouse operations through
    write-ahead logging with crash recovery support.

    Usage::

        txn_log = TransactionLog(log_dir="data/lakehouse/txn_log")
        txn_log.begin_transaction()
        txn_log.append(LogEntryType.ADD_FILE, data={"file_id": "..."})
        txn_log.commit_transaction()
    """

    def __init__(self, log_dir: str = "data/lakehouse/txn_log") -> None:
        self.log_dir = log_dir
        self._entries: List[LogEntry] = []
        self._sequence: int = 0
        self._active_transaction: Optional[str] = None
        self._checkpoints: List[CheckpointInfo] = []
        self._last_checkpoint: Optional[CheckpointInfo] = None

        os.makedirs(log_dir, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Transaction Management
    # ------------------------------------------------------------------

    def begin_transaction(self) -> str:
        """Start a new transaction.

        Returns:
            Transaction ID.
        """
        if self._active_transaction:
            self.abort_transaction()

        txn_id = str(uuid.uuid4())
        self._active_transaction = txn_id
        self._append(LogEntryType.BEGIN, {"transaction_id": txn_id}, txn_id)
        return txn_id

    def commit_transaction(self) -> bool:
        """Commit the active transaction.

        Returns:
            True if committed.
        """
        if not self._active_transaction:
            return False

        txn_id = self._active_transaction
        self._append(LogEntryType.COMMIT, {"transaction_id": txn_id}, txn_id)
        self._active_transaction = None
        self._flush()
        return True

    def abort_transaction(self) -> bool:
        """Abort/rollback the active transaction.

        Returns:
            True if aborted.
        """
        if not self._active_transaction:
            return False

        txn_id = self._active_transaction
        self._append(LogEntryType.ABORT, {"transaction_id": txn_id}, txn_id)
        self._active_transaction = None
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Log Operations
    # ------------------------------------------------------------------

    def append(
        self,
        entry_type: LogEntryType,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[LogEntry]:
        """Append an entry to the active transaction.

        Args:
            entry_type: Type of log entry.
            data: Entry data.

        Returns:
            LogEntry, or None if no active transaction.
        """
        if not self._active_transaction:
            return None
        return self._append(entry_type, data or {}, self._active_transaction)

    def _append(
        self,
        entry_type: LogEntryType,
        data: Dict[str, Any],
        txn_id: str,
    ) -> LogEntry:
        """Internal append."""
        self._sequence += 1
        entry = LogEntry(
            entry_id=str(uuid.uuid4()),
            sequence_number=self._sequence,
            entry_type=entry_type,
            transaction_id=txn_id,
            data=data,
        )
        self._entries.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def recover(self) -> List[str]:
        """Recover from crash by replaying committed transactions.

        Returns:
            List of recovered transaction IDs.
        """
        recovered: List[str] = []
        active_txns: Dict[str, List[LogEntry]] = {}

        # Group entries by transaction
        for entry in self._entries:
            active_txns.setdefault(entry.transaction_id, []).append(entry)

        for txn_id, entries in active_txns.items():
            last_entry = entries[-1] if entries else None
            if last_entry and last_entry.entry_type == LogEntryType.COMMIT:
                recovered.append(txn_id)
            # Incomplete transactions are discarded (rolled back)

        return recovered

    def replay_from_checkpoint(
        self, sequence_number: Optional[int] = None
    ) -> List[LogEntry]:
        """Replay log entries from a checkpoint.

        Args:
            sequence_number: Starting sequence number.

        Returns:
            List of LogEntry to replay.
        """
        start = sequence_number or (self._last_checkpoint.sequence_number if self._last_checkpoint else 0)
        return [e for e in self._entries if e.sequence_number > start]

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------

    def checkpoint(self, snapshot_id: str = "") -> CheckpointInfo:
        """Create a checkpoint.

        Writes a checkpoint entry to the log, allowing recovery
        to skip earlier entries.

        Args:
            snapshot_id: Associated snapshot ID.

        Returns:
            CheckpointInfo.
        """
        checkpoint = CheckpointInfo(
            sequence_number=self._sequence,
            timestamp=datetime.utcnow(),
            snapshot_id=snapshot_id,
            file_count=len(self._entries),
        )

        # Write checkpoint entry
        self._append(
            LogEntryType.CHECKPOINT,
            {
                "sequence_number": checkpoint.sequence_number,
                "snapshot_id": snapshot_id,
            },
            "system",
        )

        self._checkpoints.append(checkpoint)
        self._last_checkpoint = checkpoint
        self._flush()
        return checkpoint

    def get_last_checkpoint(self) -> Optional[CheckpointInfo]:
        """Get the last checkpoint."""
        return self._last_checkpoint

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_entries(
        self,
        transaction_id: Optional[str] = None,
        entry_type: Optional[LogEntryType] = None,
        since_sequence: Optional[int] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Query log entries.

        Args:
            transaction_id: Filter by transaction.
            entry_type: Filter by entry type.
            since_sequence: Filter by sequence number.
            limit: Maximum entries.

        Returns:
            List of LogEntry.
        """
        results = list(self._entries)

        if transaction_id:
            results = [e for e in results if e.transaction_id == transaction_id]
        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        if since_sequence is not None:
            results = [e for e in results if e.sequence_number > since_sequence]

        results.sort(key=lambda e: e.sequence_number, reverse=True)
        return results[:limit]

    def get_current_sequence(self) -> int:
        """Get the current sequence number."""
        return self._sequence

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self, older_than_sequence: Optional[int] = None) -> int:
        """Compact the log by removing entries before a checkpoint.

        Args:
            older_than_sequence: Remove entries before this sequence.

        Returns:
            Number of entries removed.
        """
        if self._last_checkpoint:
            cutoff = older_than_sequence or self._last_checkpoint.sequence_number
        else:
            cutoff = older_than_sequence or 0

        before = len(self._entries)
        self._entries = [e for e in self._entries if e.sequence_number > cutoff]
        removed = before - len(self._entries)
        self._flush()
        return removed

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get transaction log statistics."""
        type_counts: Dict[str, int] = {}
        for entry in self._entries:
            et = entry.entry_type.value
            type_counts[et] = type_counts.get(et, 0) + 1

        return {
            "total_entries": len(self._entries),
            "current_sequence": self._sequence,
            "active_transaction": self._active_transaction,
            "checkpoints": len(self._checkpoints),
            "last_checkpoint_sequence": (
                self._last_checkpoint.sequence_number if self._last_checkpoint else 0
            ),
            "by_type": type_counts,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load log state from disk."""
        log_path = os.path.join(self.log_dir, "wal.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    state = json.load(f)

                self._sequence = state.get("sequence", 0)
                self._entries = [
                    LogEntry.from_dict(e) for e in state.get("entries", [])
                ]

                for cp_data in state.get("checkpoints", []):
                    cp = CheckpointInfo(
                        sequence_number=cp_data["sequence_number"],
                        timestamp=datetime.fromisoformat(cp_data["timestamp"]),
                        snapshot_id=cp_data.get("snapshot_id", ""),
                        file_count=cp_data.get("file_count", 0),
                    )
                    self._checkpoints.append(cp)
                    self._last_checkpoint = cp
            except (json.JSONDecodeError, KeyError):
                pass

    def _flush(self) -> None:
        """Persist log state to disk."""
        state = {
            "sequence": self._sequence,
            "entries": [e.to_dict() for e in self._entries],
            "checkpoints": [
                {
                    "sequence_number": cp.sequence_number,
                    "timestamp": cp.timestamp.isoformat(),
                    "snapshot_id": cp.snapshot_id,
                    "file_count": cp.file_count,
                }
                for cp in self._checkpoints
            ],
            "updated_at": datetime.utcnow().isoformat(),
        }

        log_path = os.path.join(self.log_dir, "wal.json")
        with open(log_path, "w") as f:
            json.dump(state, f, indent=2, default=str)
