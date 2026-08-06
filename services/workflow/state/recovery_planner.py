"""Recovery planner — selects the optimal recovery strategy.

Strategies: Latest Checkpoint, Latest Snapshot, Full Replay, Incremental Replay.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .checkpoint_manager import CheckpointManager
from .snapshot_manager import SnapshotManager
from .wal import WAL
from .journal import Journal

logger = logging.getLogger(__name__)


class RecoveryStrategy(str, Enum):
    """Available recovery strategies."""

    LATEST_CHECKPOINT = "latest_checkpoint"
    LATEST_SNAPSHOT = "latest_snapshot"
    FULL_REPLAY = "full_replay"
    INCREMENTAL_REPLAY = "incremental_replay"
    NONE = "none"


class RecoveryPlanner:
    """Plans the optimal recovery strategy based on available data.

    Priority:
      1. Latest snapshot (least replay needed)
      2. Latest checkpoint (some replay needed)
      3. Full replay from journal (slowest but most complete)
    """

    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        wal: Optional[WAL] = None,
        journal: Optional[Journal] = None,
    ):
        self._checkpoint_mgr = checkpoint_manager or CheckpointManager()
        self._snapshot_mgr = snapshot_manager or SnapshotManager()
        self._wal = wal or WAL()
        self._journal = journal or Journal()

    async def plan_recovery(self, execution_id: str) -> Tuple[RecoveryStrategy, Dict[str, Any]]:
        """Determine the best recovery strategy and return context data.

        Returns:
          (strategy, context) where context contains:
            - checkpoint_version, snapshot_version, last_lsn
        """
        context: Dict[str, Any] = {}

        # Check snapshot availability
        snapshot = await self._snapshot_mgr.get_latest_snapshot(execution_id)
        if snapshot is not None:
            context["snapshot_version"] = snapshot.version
            context["snapshot_events_to_replay"] = 0  # Will be populated by engine
            logger.info("Recovery plan for %s: %s v%d", execution_id, RecoveryStrategy.LATEST_SNAPSHOT, snapshot.version)
            return RecoveryStrategy.LATEST_SNAPSHOT, context

        # Check checkpoint availability
        checkpoint = await self._checkpoint_mgr.restore_latest(execution_id)
        if checkpoint is not None:
            context["checkpoint_version"] = checkpoint.version
            context["last_lsn"] = await self._wal.get_last_lsn(execution_id)
            logger.info("Recovery plan for %s: %s v%d", execution_id, RecoveryStrategy.LATEST_CHECKPOINT, checkpoint.version)
            return RecoveryStrategy.LATEST_CHECKPOINT, context

        # Check if incremental replay is possible
        last_seq = await self._journal.get_last_sequence(execution_id)
        if last_seq > 0:
            context["last_sequence"] = last_seq
            logger.info("Recovery plan for %s: %s (seq=%d)", execution_id, RecoveryStrategy.FULL_REPLAY, last_seq)
            return RecoveryStrategy.FULL_REPLAY, context

        logger.warning("No recovery data available for %s", execution_id)
        return RecoveryStrategy.NONE, context

    async def estimate_recovery_time(
        self, execution_id: str
    ) -> Optional[float]:
        """Estimate recovery time in seconds based on available data."""
        strategy, context = await self.plan_recovery(execution_id)

        if strategy == RecoveryStrategy.NONE:
            return None

        events_count = context.get("snapshot_events_to_replay", 0)
        if strategy == RecoveryStrategy.LATEST_SNAPSHOT:
            # Fast: snapshot + few events
            return 0.1 + events_count * 0.01
        elif strategy == RecoveryStrategy.LATEST_CHECKPOINT:
            # Medium: checkpoint + WAL entries
            lsn = context.get("last_lsn", 0)
            return 0.2 + lsn * 0.005
        elif strategy == RecoveryStrategy.FULL_REPLAY:
            # Slow: reapply all journal entries
            last_seq = context.get("last_sequence", 0)
            return 0.5 + last_seq * 0.01

        return 1.0
