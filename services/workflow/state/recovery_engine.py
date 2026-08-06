"""Recovery engine — automatic crash recovery for workflow instances.

Recovery pipeline:
  1. Detect crashed/unfinished workflows
  2. Load latest snapshot
  3. Replay WAL entries after snapshot
  4. Replay journal entries after checkpoint
  5. Consistency check
  6. Resume execution
"""

from __future__ import annotations

import logging
from typing import Optional

from .workflow_state import WorkflowExecutionStatus, WorkflowState
from .snapshot_manager import SnapshotManager
from .wal import WAL, WALEntryStatus
from .journal import Journal
from .replay_engine import ReplayEngine
from .consistency_checker import ConsistencyChecker
from .state_machine import WorkflowStateMachine
from .lifecycle import LifecycleManager

logger = logging.getLogger(__name__)


class RecoveryEngine:
    """Automatic workflow recovery engine.

    Recovery pipeline:
      Crash → Load Snapshot → Replay WAL → Replay Journal → Consistency Check → Resume
    """

    def __init__(
        self,
        snapshot_manager: Optional[SnapshotManager] = None,
        wal: Optional[WAL] = None,
        journal: Optional[Journal] = None,
        replay_engine: Optional[ReplayEngine] = None,
        consistency_checker: Optional[ConsistencyChecker] = None,
        state_machine: Optional[WorkflowStateMachine] = None,
        lifecycle_manager: Optional[LifecycleManager] = None,
    ):
        self._snapshot_mgr = snapshot_manager or SnapshotManager()
        self._wal = wal or WAL()
        self._journal = journal or Journal()
        self._replay = replay_engine or ReplayEngine()
        self._consistency = consistency_checker or ConsistencyChecker()
        self._state_machine = state_machine or WorkflowStateMachine()
        self._lifecycle = lifecycle_manager

    # ---- Recovery pipeline --------------------------------------------------

    async def recover(self, execution_id: str) -> Optional[WorkflowState]:
        """Execute the full recovery pipeline for a crashed workflow.

        Returns recovered state ready for resumption, or None if unrecoverable.
        """
        logger.info("Starting recovery for execution %s", execution_id)

        # 1. Load latest snapshot
        snapshot = await self._snapshot_mgr.get_latest_snapshot(execution_id)
        state_dict = None

        if snapshot is not None:
            state_dict = self._snapshot_mgr.restore_state(snapshot)
            logger.info("Snapshot loaded: exec=%s version=%d", execution_id, snapshot.version)

        # Also try rebuilding from journal if no snapshot
        state = await self._replay.replay_from_journal(execution_id)
        if state is None and state_dict is not None:
            # Had snapshot but journal replay failed — try to reconstruct
            state = WorkflowState(
                execution_id=execution_id,
                status=WorkflowExecutionStatus(state_dict.get("status", WorkflowExecutionStatus.SUSPENDED.value)),
            )
        elif state is None:
            logger.error("No state available for recovery: %s", execution_id)
            return None

        # 2. Consistency check
        issues = self._consistency.check(state)
        if issues:
            logger.warning("Consistency issues found: %s", issues)
            repaired = self._consistency.repair(state, issues)
            if not repaired:
                logger.error("Unrecoverable consistency issues for %s", execution_id)
                return None

        # 3. Resume workflow
        await self._journal.record_recovery_started(execution_id)
        success = await self._state_machine.recover(state)
        await self._journal.record_recovery_completed(execution_id)

        if success:
            logger.info("Recovery successful: exec=%s", execution_id)
            return state

        logger.error("Recovery failed: exec=%s", execution_id)
        return None

    async def scan_and_recover(self) -> int:
        """Scan for crashed instances and recover them. Returns count recovered."""
        # In production, this would scan persistent storage for non-terminal workflows
        # For now, scan lifecycle manager for active instances
        if self._lifecycle is None:
            return 0

        recovered = 0
        active = self._lifecycle.get_active_instances()
        for eid, state in active.items():
            if state.status == WorkflowExecutionStatus.SUSPENDED:
                result = await self.recover(eid)
                if result:
                    recovered += 1

        logger.info("Recovery scan complete: %d recovered", recovered)
        return recovered
