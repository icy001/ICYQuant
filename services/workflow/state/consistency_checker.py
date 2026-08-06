"""Consistency checker — validates and repairs workflow state consistency.

Checks: Workflow State ↔ Node State ↔ Journal ↔ Checkpoint ↔ Variables
On finding issues: repair or safe-stop.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .workflow_state import WorkflowExecutionStatus, WorkflowState
from .node_state import NodeExecutionStatus
from .state_validator import StateValidator

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """Validates cross-component consistency and attempts repairs."""

    def __init__(self):
        self._state_validator = StateValidator()

    # ---- Check --------------------------------------------------------------

    def check(self, state: WorkflowState) -> List[str]:
        """Run all consistency checks. Returns list of issues (empty = healthy)."""
        issues: List[str] = []

        # Use state validator for basic checks
        issues.extend(self._state_validator.validate_consistency(state))

        # Check node state integrity
        issues.extend(self._check_node_integrity(state))

        # Check variable integrity
        issues.extend(self._check_variables(state))

        # Check status integrity
        issues.extend(self._check_status_integrity(state))

        return issues

    def _check_node_integrity(self, state: WorkflowState) -> List[str]:
        issues = []
        for node_id, ns in state.node_states.items():
            # Node status should be valid for its parent workflow status
            if state.status == WorkflowExecutionStatus.COMPLETED and not ns.is_terminal():
                issues.append(f"Wf completed but node {node_id} is {ns.status.value}")
            # Node attempt count should be consistent with retries
            if ns.status == NodeExecutionStatus.RETRYING and not ns.can_retry():
                issues.append(f"Node {node_id} retrying but exceeded max attempts")
        return issues

    def _check_variables(self, state: WorkflowState) -> List[str]:
        issues = []
        # Check for null but required variable patterns
        for key, value in state.variables.items():
            if value is None:
                issues.append(f"Variable {key} is null")
        return issues

    def _check_status_integrity(self, state: WorkflowState) -> List[str]:
        issues = []
        # Validate status enum membership
        try:
            WorkflowExecutionStatus(state.status.value)
        except ValueError:
            issues.append(f"Invalid workflow status: {state.status}")

        for node_id, ns in state.node_states.items():
            try:
                NodeExecutionStatus(ns.status.value)
            except ValueError:
                issues.append(f"Invalid node status for {node_id}: {ns.status}")
        return issues

    # ---- Repair -------------------------------------------------------------

    def repair(self, state: WorkflowState, issues: List[str]) -> bool:
        """Attempt to repair consistency issues.

        Returns True if all issues were repaired, False if some are unfixable.
        """
        if not issues:
            return True

        logger.warning("Attempting to repair %d consistency issues for %s", len(issues), state.execution_id)

        all_repaired = True

        for issue in issues:
            repaired = self._attempt_repair(state, issue)
            if not repaired:
                logger.error("Unrepairable issue: %s", issue)
                all_repaired = False

        if all_repaired:
            logger.info("All consistency issues repaired for %s", state.execution_id)
        else:
            logger.error(
                "Some issues unrepairable for %s — safe stop recommended",
                state.execution_id,
            )

        return all_repaired

    def _attempt_repair(self, state: WorkflowState, issue: str) -> bool:
        """Try to repair a single consistency issue."""
        if "completed but node" in issue:
            # Mark stuck nodes as cancelled
            for ns in state.node_states.values():
                if not ns.is_terminal():
                    ns.status = NodeExecutionStatus.CANCELLED
            return True

        if "RUNNING but has no active" in issue:
            # All nodes finished but workflow still running — complete it
            state.status = WorkflowExecutionStatus.COMPLETED
            state.touch()
            return True

        return False
