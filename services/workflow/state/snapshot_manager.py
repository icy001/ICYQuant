"""Snapshot manager — full and incremental workflow snapshots.

Saves complete workflow state for recovery, debugging, and audit.
Supports compression and object storage integration.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from .workflow_state import WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """A full or incremental snapshot of workflow state."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    version: int = 0
    snapshot_type: str = "full"  # "full" or "incremental"
    base_snapshot_id: Optional[str] = None  # for incremental snapshots
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    compressed: bool = False
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "execution_id": self.execution_id,
            "version": self.version,
            "snapshot_type": self.snapshot_type,
            "base_snapshot_id": self.base_snapshot_id,
            "workflow_state": self.workflow_state,
            "created_at": self.created_at.isoformat(),
            "compressed": self.compressed,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
        }


class SnapshotManager:
    """Manages workflow snapshots for persistence and recovery.

    Snapshots capture the complete workflow state at a moment in time.
    Supports both full and incremental snapshots with optional compression.
    """

    def __init__(
        self,
        storage_backend: Optional[Any] = None,  # Object storage interface
        compress: bool = True,
    ):
        self._storage = storage_backend
        self._compress = compress
        self._snapshots: Dict[str, Dict[int, Snapshot]] = {}
        self._version_counters: Dict[str, int] = {}

    # ---- Create snapshot ----------------------------------------------------

    async def create_full_snapshot(
        self,
        state: WorkflowState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Snapshot:
        """Create a full snapshot of workflow state."""
        version = self._next_version(state.execution_id)
        state_dict = state.to_dict()

        snapshot = Snapshot(
            execution_id=state.execution_id,
            version=version,
            snapshot_type="full",
            workflow_state=state_dict,
            metadata=metadata or {},
        )

        if self._compress:
            snapshot = await self._compress_snapshot(snapshot)

        snapshot.size_bytes = len(json.dumps(snapshot.to_dict()))
        await self._store_snapshot(snapshot)

        logger.info(
            "Full snapshot created: exec=%s v%d size=%d",
            state.execution_id, version, snapshot.size_bytes,
        )
        return snapshot

    async def create_incremental_snapshot(
        self,
        state: WorkflowState,
        base_snapshot_id: str,
        changed_keys: Optional[List[str]] = None,
    ) -> Snapshot:
        """Create an incremental snapshot containing only changed data."""
        version = self._next_version(state.execution_id)
        state_dict = state.to_dict()

        if changed_keys:
            # Only include changed portions
            incremental_state = {k: v for k, v in state_dict.items() if k in changed_keys}
        else:
            incremental_state = state_dict

        snapshot = Snapshot(
            execution_id=state.execution_id,
            version=version,
            snapshot_type="incremental",
            base_snapshot_id=base_snapshot_id,
            workflow_state=incremental_state,
        )

        snapshot.size_bytes = len(json.dumps(snapshot.to_dict()))
        await self._store_snapshot(snapshot)

        logger.info(
            "Incremental snapshot created: exec=%s v%d base=%s",
            state.execution_id, version, base_snapshot_id,
        )
        return snapshot

    # ---- Retrieve snapshot --------------------------------------------------

    async def get_snapshot(self, execution_id: str, version: int) -> Optional[Snapshot]:
        """Get a specific snapshot version."""
        return self._snapshots.get(execution_id, {}).get(version)

    async def get_latest_snapshot(self, execution_id: str) -> Optional[Snapshot]:
        """Get the latest snapshot for an execution."""
        versions = self._snapshots.get(execution_id, {})
        if not versions:
            return None
        return versions[max(versions.keys())]

    async def list_snapshots(self, execution_id: str) -> List[Snapshot]:
        """List all snapshots for an execution, newest first."""
        versions = self._snapshots.get(execution_id, {})
        return sorted(versions.values(), key=lambda s: s.version, reverse=True)

    # ---- Apply snapshot -----------------------------------------------------

    def restore_state(self, snapshot: Snapshot) -> Dict[str, Any]:
        """Restore workflow state dict from a snapshot."""
        state_dict = snapshot.workflow_state
        if snapshot.compressed:
            state_dict = self._decompress_state(state_dict)
        return state_dict

    # ---- Internal -----------------------------------------------------------

    async def _store_snapshot(self, snapshot: Snapshot) -> None:
        eid = snapshot.execution_id
        if eid not in self._snapshots:
            self._snapshots[eid] = {}
        self._snapshots[eid][snapshot.version] = snapshot

        # If storage backend is available, persist externally
        if self._storage and hasattr(self._storage, "put"):
            try:
                key = f"snapshots/{eid}/{snapshot.version}.json"
                data = json.dumps(snapshot.to_dict()).encode("utf-8")
                if snapshot.compressed:
                    data = gzip.compress(data)
                await self._storage.put(key, data)
            except Exception:
                logger.exception("Failed to persist snapshot to storage")

    async def _compress_snapshot(self, snapshot: Snapshot) -> Snapshot:
        compressed_state = self._compress_state(snapshot.workflow_state)
        snapshot.workflow_state = compressed_state
        snapshot.compressed = True
        return snapshot

    @staticmethod
    def _compress_state(state: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(state).encode("utf-8")
        compressed = gzip.compress(data)
        return {"__compressed__": True, "data_b64": compressed.hex()}

    @staticmethod
    def _decompress_state(state: Dict[str, Any]) -> Dict[str, Any]:
        if not state.get("__compressed__"):
            return state
        data = bytes.fromhex(state["data_b64"])
        decompressed = gzip.decompress(data)
        return json.loads(decompressed.decode("utf-8"))

    def _next_version(self, execution_id: str) -> int:
        current = self._version_counters.get(execution_id, 0)
        self._version_counters[execution_id] = current + 1
        return self._version_counters[execution_id]
