"""State validation — enforces valid transitions and consistency rules."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from .workflow_state import (
    WorkflowExecutionStatus,
    WorkflowState,
    VALID_WORKFLOW_TRANSITIONS,
)
from .node_state import (
    NodeExecutionStatus,
    NodeState,
    VALID_NODE_TRANSITIONS,
)

logger = logging.getLogger(__name__)


class StateValidator:
    """Validates state transitions and cross-state consistency."""

    # ---- Workflow transition validation -------------------------------------

    def validate_workflow_transition(
        self,
        state: WorkflowState,
        target: WorkflowExecutionStatus,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a workflow can move from current status to target."""
        current = state.status

        # Check transition table
        valid_targets = VALID_WORKFLOW_TRANSITIONS.get(current, set())
        if target not in valid_targets:
            return False, (
                f"Invalid workflow transition: {current.value} → {target.value}. "
                f"Valid targets: {[t.value for t in valid_targets]}"
            )

        # Cannot transition from terminal
        if current.is_terminal():
            return False, f"Cannot transition from terminal state: {current.value}"

        # Only FAILED/SUSPENDED can recover to RUNNING
        if target == WorkflowExecutionStatus.RUNNING and current == WorkflowExecutionStatus.COMPLETED:
            return False, "Cannot restart a completed workflow"

        return True, None

    # ---- Node transition validation -----------------------------------------

    def validate_node_transition(
        self,
        node_state: NodeState,
        target: NodeExecutionStatus,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a node can move from current status to target."""
        current = node_state.status

        valid_targets = VALID_NODE_TRANSITIONS.get(current, set())
        if target not in valid_targets:
            return False, (
                f"Invalid node transition: {current.value} → {target.value}. "
                f"Valid targets: {[t.value for t in valid_targets]}"
            )

        if current.is_terminal():
            return False, f"Cannot transition from terminal node state: {current.value}"

        # Retry requires remaining attempts
        if target == NodeExecutionStatus.RETRYING and not node_state.can_retry():
            return False, (
                f"Node {node_state.node_id} exhausted retries "
                f"({node_state.attempt}/{node_state.max_attempts})"
            )

        return True, None

    # ---- Cross-state consistency --------------------------------------------

    def validate_consistency(self, state: WorkflowState) -> list[str]:
        """Check consistency between workflow state and all node states.

        Returns a list of inconsistencies (empty = all good).
        """
        issues = []

        # Workflow terminal implies all nodes terminal
        if state.status.is_terminal():
            for ns in state.node_states.values():
                if not ns.is_terminal():
                    issues.append(
                        f"Workflow is {state.status.value} but node {ns.node_id} is {ns.status.value}"
                    )

        # Workflow RUNNING requires at least one active or pending node
        if state.status == WorkflowExecutionStatus.RUNNING:
            active_nodes = [
                nid for nid, ns in state.node_states.items()
                if ns.status in NodeExecutionStatus.active_states() or ns.status == NodeExecutionStatus.PENDING
            ]
            if not active_nodes and state.node_states:
                issues.append("Workflow is RUNNING but has no active or pending nodes")

        return issues
