"""Checkpoint manager — save and restore workflow execution progress.

Supports: manual, periodic, node-finish, and before-critical-step checkpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from .workflow_state import WorkflowExecutionStatus, WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """A snapshot of workflow execution state at a point in time."""

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    version: int = 0
    workflow_status: str = ""
    node_states: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    compressed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "execution_id": self.execution_id,
            "version": self.version,
            "workflow_status": self.workflow_status,
            "node_states": self.node_states,
            "variables": self.variables,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "compressed": self.compressed,
        }


class CheckpointManager:
    """Manages checkpoints for workflow execution instances.

    Checkpoint types:
      - manual: explicitly triggered by user/code
      - periodic: time-based interval
      - node_finish: after each node completes
      - critical: before a critical step begins
    """

    def __init__(self, repository: Optional["CheckpointRepository"] = None):
        self._repository = repository or CheckpointRepository()
        self._version_counters: Dict[str, int] = {}

    # ---- Create checkpoint --------------------------------------------------

    async def create_checkpoint(
        self,
        state: WorkflowState,
        trigger: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """Create a checkpoint from the current workflow state."""
        version = self._next_version(state.execution_id)

        checkpoint = Checkpoint(
            execution_id=state.execution_id,
            version=version,
            workflow_status=state.status.value,
            node_states={k: v.to_dict() for k, v in state.node_states.items()},
            variables=dict(state.variables),
            metadata=metadata or {"trigger": trigger},
        )

        await self._repository.save(checkpoint)
        logger.info(
            "Checkpoint created: exec=%s version=%d trigger=%s",
            state.execution_id, version, trigger,
        )
        return checkpoint

    # ---- Restore from checkpoint --------------------------------------------

    async def restore_latest(self, execution_id: str) -> Optional[Checkpoint]:
        """Restore the latest checkpoint for an execution."""
        return await self._repository.get_latest(execution_id)

    async def restore_version(
        self, execution_id: str, version: int
    ) -> Optional[Checkpoint]:
        """Restore a specific checkpoint version."""
        return await self._repository.get_version(execution_id, version)

    async def list_checkpoints(self, execution_id: str) -> List[Checkpoint]:
        """List all checkpoints for an execution."""
        return await self._repository.list_for_execution(execution_id)

    # ---- Apply checkpoint to state ------------------------------------------

    def apply_checkpoint(self, state: WorkflowState, checkpoint: Checkpoint) -> None:
        """Apply a checkpoint to restore workflow state."""
        state.status = WorkflowExecutionStatus(checkpoint.workflow_status)
        state.variables = dict(checkpoint.variables)
        # Node states restored as dicts — caller should rebuild NodeState objects
        logger.info(
            "Checkpoint applied: exec=%s version=%d",
            state.execution_id, checkpoint.version,
        )

    # ---- Cleanup ------------------------------------------------------------

    async def prune_old(
        self, execution_id: str, keep_last: int = 10
    ) -> int:
        """Remove old checkpoints, keeping only the most recent N."""
        return await self._repository.prune(execution_id, keep_last)

    # ---- Internal -----------------------------------------------------------

    def _next_version(self, execution_id: str) -> int:
        current = self._version_counters.get(execution_id, 0)
        self._version_counters[execution_id] = current + 1
        return self._version_counters[execution_id]
