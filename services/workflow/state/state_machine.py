"""Unified state machine — drives workflow and node state transitions.

The StateMachine is the authoritative coordinator for all state
changes within a workflow instance. Every transition goes through
the transition manager, is validated, then persisted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .workflow_state import WorkflowExecutionStatus, WorkflowState
from .node_state import NodeExecutionStatus, NodeState
from .transition_manager import TransitionManager
from .state_validator import StateValidator

logger = logging.getLogger(__name__)


class WorkflowStateMachine:
    """Unified state machine for workflow and node transitions.

    Every transition is:
      1. Validated against the transition table
      2. Checked for consistency
      3. Applied atomically via TransitionManager
      4. Persisted to WAL/Journal (by the calling engine layer)
    """

    def __init__(
        self,
        transition_manager: Optional[TransitionManager] = None,
        state_validator: Optional[StateValidator] = None,
        event_bus: Optional[Any] = None,
    ):
        self._transitions = transition_manager or TransitionManager()
        self._validator = state_validator or StateValidator()
        self._event_bus = event_bus

    # ---- Workflow-level transitions ----------------------------------------

    async def transition_workflow(
        self,
        state: WorkflowState,
        to_status: WorkflowExecutionStatus,
        reason: Optional[str] = None,
    ) -> bool:
        """Transition workflow to a new status."""
        from_status = state.status

        # Validate
        valid, err = self._validator.validate_workflow_transition(state, to_status)
        if not valid:
            logger.error("Workflow transition rejected: %s", err)
            return False

        # Apply
        await self._transitions.record_workflow_transition(
            state.execution_id, from_status, to_status, reason
        )
        state.status = to_status
        state.touch()

        if to_status == WorkflowExecutionStatus.RUNNING and state.started_at is None:
            state.started_at = datetime.now(timezone.utc)
        if to_status.is_terminal():
            state.completed_at = datetime.now(timezone.utc)

        self._emit_workflow_event(state, from_status, to_status, reason)
        logger.info("Workflow %s: %s → %s", state.execution_id, from_status.value, to_status.value)
        return True

    # ---- Node-level transitions --------------------------------------------

    async def transition_node(
        self,
        workflow_state: WorkflowState,
        node_id: str,
        to_status: NodeExecutionStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Transition a node within a workflow instance."""
        if node_id not in workflow_state.node_states:
            logger.error("Node %s not found in workflow %s", node_id, workflow_state.execution_id)
            return False

        node_state = workflow_state.node_states[node_id]
        from_status = node_state.status

        valid, err = self._validator.validate_node_transition(node_state, to_status)
        if not valid:
            logger.error("Node transition rejected: %s", err)
            return False

        await self._transitions.record_node_transition(
            workflow_state.execution_id, node_id, from_status, to_status, error_message
        )
        node_state.status = to_status
        node_state.touch()
        if error_message:
            node_state.error_message = error_message

        if to_status in (NodeExecutionStatus.RUNNING, NodeExecutionStatus.DISPATCHED) and node_state.started_at is None:
            node_state.started_at = datetime.now(timezone.utc)
        if to_status.is_terminal():
            node_state.completed_at = datetime.now(timezone.utc)

        self._emit_node_event(workflow_state.execution_id, node_id, from_status, to_status, error_message)
        logger.info(
            "Node %s/%s: %s → %s",
            workflow_state.execution_id, node_id, from_status.value, to_status.value,
        )
        return True

    # ---- Rollback -----------------------------------------------------------

    async def rollback(
        self,
        state: WorkflowState,
        to_status: WorkflowExecutionStatus,
    ) -> bool:
        """Force rollback to a prior state (for error recovery)."""
        if state.status.is_terminal():
            logger.warning("Cannot rollback terminal workflow %s", state.execution_id)
            return False
        return await self.transition_workflow(state, to_status, reason="rollback")

    # ---- Recovery -----------------------------------------------------------

    async def recover(self, state: WorkflowState) -> bool:
        """Attempt to recover a workflow from SUSPENDED/WAITING/FAILED."""
        if state.status not in WorkflowExecutionStatus.resumable_states():
            return False
        return await self.transition_workflow(state, WorkflowExecutionStatus.RUNNING, reason="recovery")

    # ---- Internal -----------------------------------------------------------

    def _emit_workflow_event(
        self,
        state: WorkflowState,
        from_status: WorkflowExecutionStatus,
        to_status: WorkflowExecutionStatus,
        reason: Optional[str],
    ) -> None:
        self._emit("workflow_state_changed", {
            "execution_id": state.execution_id,
            "workflow_name": state.workflow_name,
            "from": from_status.value,
            "to": to_status.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _emit_node_event(
        self,
        execution_id: str,
        node_id: str,
        from_status: NodeExecutionStatus,
        to_status: NodeExecutionStatus,
        error_message: Optional[str],
    ) -> None:
        self._emit("node_state_changed", {
            "execution_id": execution_id,
            "node_id": node_id,
            "from": from_status.value,
            "to": to_status.value,
            "error": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, data)
            except Exception:
                logger.exception("Failed to emit event: %s", event_type)
