"""
Memory snapshot for agent state persistence and recovery.

Captures complete agent state snapshots including conversation,
planning state, execution state, and memory layers for recovery.

Pipeline:
    Conversation → Planning State → Execution State → Snapshot → Recovery
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Snapshot Types ──


class SnapshotType(str, Enum):
    """Types of snapshots."""

    FULL = "full"                   # Complete state capture
    INCREMENTAL = "incremental"     # Delta since last snapshot
    CHECKPOINT = "checkpoint"       # Recovery checkpoint
    ARCHIVE = "archive"             # Long-term archival


@dataclass
class MemorySnapshot:
    """Complete agent state snapshot for persistence and recovery.

    Captures all memory layers, planning state, and execution state
    at a point in time.
    """

    snapshot_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    snapshot_type: SnapshotType = SnapshotType.FULL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── State Captures ──
    conversation: List[Dict[str, Any]] = field(default_factory=list)
    planning_state: Dict[str, Any] = field(default_factory=dict)
    execution_state: Dict[str, Any] = field(default_factory=dict)

    # ── Memory State ──
    working_memory: Dict[str, Any] = field(default_factory=dict)
    short_term_memory_refs: List[str] = field(default_factory=list)
    long_term_memory_refs: List[str] = field(default_factory=list)
    semantic_node_ids: List[str] = field(default_factory=list)
    episode_ids: List[str] = field(default_factory=list)

    # ── Metadata ──
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to serializable dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "snapshot_type": self.snapshot_type.value,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "conversation": self.conversation,
            "planning_state": self.planning_state,
            "execution_state": self.execution_state,
            "working_memory": self.working_memory,
            "short_term_memory_refs": self.short_term_memory_refs,
            "long_term_memory_refs": self.long_term_memory_refs,
            "semantic_node_ids": self.semantic_node_ids,
            "episode_ids": self.episode_ids,
            "metadata": self.metadata,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemorySnapshot":
        """Restore snapshot from dictionary."""
        return cls(
            snapshot_id=data.get("snapshot_id", uuid4().hex),
            session_id=data.get("session_id", ""),
            snapshot_type=SnapshotType(data.get("snapshot_type", "full")),
            created_at=datetime.fromisoformat(data["created_at"]),
            conversation=data.get("conversation", []),
            planning_state=data.get("planning_state", {}),
            execution_state=data.get("execution_state", {}),
            working_memory=data.get("working_memory", {}),
            short_term_memory_refs=data.get("short_term_memory_refs", []),
            long_term_memory_refs=data.get("long_term_memory_refs", []),
            semantic_node_ids=data.get("semantic_node_ids", []),
            episode_ids=data.get("episode_ids", []),
            version=data.get("version", "1.0"),
            metadata=data.get("metadata", {}),
            checksum=data.get("checksum"),
        )

    def serialize(self) -> str:
        """Serialize snapshot to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def deserialize(cls, data: str) -> "MemorySnapshot":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(data))

    def get_summary(self) -> Dict[str, Any]:
        """Get snapshot summary."""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "type": self.snapshot_type.value,
            "created_at": self.created_at.isoformat(),
            "conversation_turns": len(self.conversation),
            "working_memory_keys": len(self.working_memory),
            "stm_refs": len(self.short_term_memory_refs),
            "ltm_refs": len(self.long_term_memory_refs),
            "semantic_nodes": len(self.semantic_node_ids),
            "episodes": len(self.episode_ids),
        }


# ── Snapshot Manager ──


class SnapshotManager:
    """Manages memory snapshot lifecycle.

    Handles snapshot creation, storage, retrieval, and recovery
    for agent state persistence.

    Usage:
        mgr = SnapshotManager(max_snapshots=100)
        snapshot = mgr.create_snapshot(session_id="s1", conversation=[], ...)
        await mgr.recover(session_id="s1")
    """

    def __init__(self, max_snapshots: int = 100) -> None:
        self.max_snapshots = max_snapshots
        self._snapshots: Dict[str, MemorySnapshot] = {}
        self._snapshots_by_session: Dict[str, List[str]] = {}
        logger.info("SnapshotManager created")

    # ── Snapshot Operations ──

    def create_snapshot(
        self,
        session_id: str,
        conversation: Optional[List[Dict[str, Any]]] = None,
        planning_state: Optional[Dict[str, Any]] = None,
        execution_state: Optional[Dict[str, Any]] = None,
        working_memory: Optional[Dict[str, Any]] = None,
        snapshot_type: SnapshotType = SnapshotType.FULL,
        **kwargs: Any,
    ) -> MemorySnapshot:
        """Create a new state snapshot.

        Args:
            session_id: Associated session.
            conversation: Conversation history.
            planning_state: Current planning state.
            execution_state: Current execution state.
            working_memory: Working memory contents.
            snapshot_type: Type of snapshot.
            **kwargs: Additional state data.

        Returns:
            The created MemorySnapshot.
        """
        snapshot = MemorySnapshot(
            session_id=session_id,
            snapshot_type=snapshot_type,
            conversation=conversation or [],
            planning_state=planning_state or {},
            execution_state=execution_state or {},
            working_memory=working_memory or {},
            metadata=kwargs.get("metadata", {}),
        )

        # Apply other state from kwargs
        if "short_term_memory_refs" in kwargs:
            snapshot.short_term_memory_refs = kwargs["short_term_memory_refs"]
        if "long_term_memory_refs" in kwargs:
            snapshot.long_term_memory_refs = kwargs["long_term_memory_refs"]
        if "semantic_node_ids" in kwargs:
            snapshot.semantic_node_ids = kwargs["semantic_node_ids"]
        if "episode_ids" in kwargs:
            snapshot.episode_ids = kwargs["episode_ids"]

        self._store_snapshot(snapshot)
        logger.info(f"Snapshot created: {snapshot.snapshot_id}")
        return snapshot

    def _store_snapshot(self, snapshot: MemorySnapshot) -> None:
        """Store snapshot and enforce capacity."""
        # Enforce max capacity
        if len(self._snapshots) >= self.max_snapshots:
            oldest = min(
                self._snapshots.values(),
                key=lambda s: s.created_at,
            )
            del self._snapshots[oldest.snapshot_id]

        self._snapshots[snapshot.snapshot_id] = snapshot
        self._snapshots_by_session.setdefault(snapshot.session_id, [])
        self._snapshots_by_session[snapshot.session_id].append(snapshot.snapshot_id)

    # ── Recovery ──

    def get_latest_snapshot(self, session_id: str) -> Optional[MemorySnapshot]:
        """Get the most recent snapshot for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Latest snapshot or None.
        """
        snapshot_ids = self._snapshots_by_session.get(session_id, [])
        if not snapshot_ids:
            return None

        latest_id = snapshot_ids[-1]
        return self._snapshots.get(latest_id)

    def get_snapshot(self, snapshot_id: str) -> Optional[MemorySnapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_session_snapshots(self, session_id: str) -> List[MemorySnapshot]:
        """Get all snapshots for a session, ordered by time."""
        ids = self._snapshots_by_session.get(session_id, [])
        return [self._snapshots[sid] for sid in ids if sid in self._snapshots]

    # ── Cleanup ──

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        snapshot = self._snapshots.pop(snapshot_id, None)
        if snapshot:
            session_snaps = self._snapshots_by_session.get(snapshot.session_id, [])
            if snapshot_id in session_snaps:
                session_snaps.remove(snapshot_id)
            return True
        return False

    def delete_session_snapshots(self, session_id: str) -> int:
        """Delete all snapshots for a session.

        Returns:
            Number of snapshots deleted.
        """
        snapshot_ids = self._snapshots_by_session.pop(session_id, [])
        for sid in snapshot_ids:
            self._snapshots.pop(sid, None)
        return len(snapshot_ids)

    # ── Status ──

    @property
    def total_snapshots(self) -> int:
        """Total stored snapshots."""
        return len(self._snapshots)

    def get_summary(self) -> Dict[str, Any]:
        """Get snapshot manager summary."""
        type_counts: Dict[str, int] = {}
        for snap in self._snapshots.values():
            t = snap.snapshot_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_snapshots": self.total_snapshots,
            "unique_sessions": len(self._snapshots_by_session),
            "by_type": type_counts,
            "max_snapshots": self.max_snapshots,
        }
