"""Execution journal — chronological record of all workflow events.

Records every step of the workflow lifecycle for full audit and replay capability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class JournalEntryType(str, Enum):
    """Types of journal entries."""

    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_SUSPENDED = "workflow_suspended"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_TIMEOUT = "workflow_timeout"

    NODE_SCHEDULED = "node_scheduled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_RETRY = "node_retry"
    NODE_TIMEOUT = "node_timeout"
    NODE_SKIPPED = "node_skipped"

    CHECKPOINT_CREATED = "checkpoint_created"
    SNAPSHOT_CREATED = "snapshot_created"
    VARIABLE_UPDATED = "variable_updated"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    ERROR = "error"


@dataclass
class JournalEntry:
    """A single entry in the execution journal."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    sequence: int = 0
    entry_type: JournalEntryType = JournalEntryType.WORKFLOW_STARTED
    node_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "execution_id": self.execution_id,
            "sequence": self.sequence,
            "entry_type": self.entry_type.value,
            "node_id": self.node_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class Journal:
    """Execution journal recording every step in the workflow lifecycle.

    The journal is the single source of truth for replay and audit.
    Every significant event is recorded with a monotonically increasing sequence number.
    """

    def __init__(self):
        self._entries: Dict[str, List[JournalEntry]] = {}
        self._sequence_counters: Dict[str, int] = {}

    # ---- Record entries -----------------------------------------------------

    async def record(
        self,
        execution_id: str,
        entry_type: JournalEntryType,
        payload: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JournalEntry:
        """Record a journal entry."""
        seq = self._next_sequence(execution_id)
        entry = JournalEntry(
            execution_id=execution_id,
            sequence=seq,
            entry_type=entry_type,
            node_id=node_id,
            payload=payload or {},
            metadata=metadata or {},
        )
        if execution_id not in self._entries:
            self._entries[execution_id] = []
        self._entries[execution_id].append(entry)
        logger.debug(
            "Journal: exec=%s seq=%d type=%s",
            execution_id, seq, entry_type.value,
        )
        return entry

    # Domain-specific helpers

    async def record_workflow_started(self, execution_id: str, metadata: Optional[Dict] = None) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.WORKFLOW_STARTED, metadata=metadata)

    async def record_workflow_completed(self, execution_id: str, result: Optional[Dict] = None) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.WORKFLOW_COMPLETED, payload=result)

    async def record_workflow_failed(self, execution_id: str, error: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.WORKFLOW_FAILED, payload={"error": error})

    async def record_node_scheduled(self, execution_id: str, node_id: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.NODE_SCHEDULED, node_id=node_id)

    async def record_node_started(self, execution_id: str, node_id: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.NODE_STARTED, node_id=node_id)

    async def record_node_completed(self, execution_id: str, node_id: str, output: Optional[Dict] = None) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.NODE_COMPLETED, node_id=node_id, payload=output)

    async def record_node_failed(self, execution_id: str, node_id: str, error: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.NODE_FAILED, node_id=node_id, payload={"error": error})

    async def record_node_retry(self, execution_id: str, node_id: str, attempt: int) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.NODE_RETRY, node_id=node_id, payload={"attempt": attempt})

    async def record_recovery_started(self, execution_id: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.RECOVERY_STARTED)

    async def record_recovery_completed(self, execution_id: str) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.RECOVERY_COMPLETED)

    async def record_error(self, execution_id: str, error: str, node_id: Optional[str] = None) -> JournalEntry:
        return await self.record(execution_id, JournalEntryType.ERROR, node_id=node_id, payload={"error": error})

    # ---- Query --------------------------------------------------------------

    async def get_entries(self, execution_id: str) -> List[JournalEntry]:
        """Return all journal entries for an execution in order."""
        return list(self._entries.get(execution_id, []))

    async def get_entries_since(
        self, execution_id: str, since_sequence: int
    ) -> List[JournalEntry]:
        """Return entries since a specific sequence number."""
        return [
            e for e in self._entries.get(execution_id, [])
            if e.sequence > since_sequence
        ]

    async def get_node_entries(
        self, execution_id: str, node_id: str
    ) -> List[JournalEntry]:
        """Return all entries for a specific node."""
        return [
            e for e in self._entries.get(execution_id, [])
            if e.node_id == node_id
        ]

    async def get_last_sequence(self, execution_id: str) -> int:
        return self._sequence_counters.get(execution_id, 0)

    # ---- Internal -----------------------------------------------------------

    def _next_sequence(self, execution_id: str) -> int:
        current = self._sequence_counters.get(execution_id, 0)
        self._sequence_counters[execution_id] = current + 1
        return self._sequence_counters[execution_id]
