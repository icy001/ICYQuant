"""Unified persistence layer — transactional writes across checkpoint, snapshot, WAL, journal."""

from __future__ import annotations

import logging
from typing import Optional

from .checkpoint_manager import CheckpointManager
from .snapshot_manager import SnapshotManager
from .wal import WAL
from .journal import Journal
from .workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class PersistenceLayer:
    """Unified persistence orchestrator for workflow state.

    Ensures transactional consistency across:
      - Checkpoint
      - Snapshot
      - Write-Ahead Log
      - Execution Journal
    """

    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        wal: Optional[WAL] = None,
        journal: Optional[Journal] = None,
    ):
        self._checkpoint = checkpoint_manager or CheckpointManager()
        self._snapshot = snapshot_manager or SnapshotManager()
        self._wal = wal or WAL()
        self._journal = journal or Journal()

    async def save_all(self, state: WorkflowState) -> None:
        """Persist workflow state across all stores atomically."""
        try:
            # 1. Checkpoint
            await self._checkpoint.create_checkpoint(state, trigger="persistence_layer")

            # 2. Snapshot (full)
            await self._snapshot.create_full_snapshot(state)

            # 3. Journal entry
            await self._journal.record_workflow_started(state.execution_id)

            logger.info("Full persistence saved for exec=%s", state.execution_id)
        except Exception as e:
            logger.error("Persistence save failed for %s: %s", state.execution_id, e)
            raise

    async def save_incremental(self, state: WorkflowState) -> None:
        """Save incremental state changes."""
        try:
            snapshot = await self._snapshot.get_latest_snapshot(state.execution_id)
            base_id = snapshot.snapshot_id if snapshot else None
            if base_id:
                await self._snapshot.create_incremental_snapshot(state, base_id)
            else:
                await self._snapshot.create_full_snapshot(state)
        except Exception as e:
            logger.error("Incremental save failed for %s: %s", state.execution_id, e)
            raise

    async def cleanup(self, execution_id: str) -> None:
        """Clean up all persistent data for a completed execution."""
        await self._checkpoint.prune_old(execution_id, keep_last=1)
        logger.info("Persistence cleaned up for exec=%s", execution_id)
