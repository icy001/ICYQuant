"""State diagnostics — inspect and debug workflow state internals."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .workflow_state import WorkflowState
from .consistency_checker import ConsistencyChecker

logger = logging.getLogger(__name__)


class StateDiagnostics:
    """Diagnostics utilities for workflow state debugging.

    Provides:
      - State inspection
      - Dump to dict for debugging
      - Consistency check reports
      - Execution summary generation
    """

    def __init__(self, consistency_checker: Optional[ConsistencyChecker] = None):
        self._consistency = consistency_checker or ConsistencyChecker()

    # ---- Inspection ---------------------------------------------------------

    def inspect(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate a comprehensive inspection report."""
        node_details = {}
        for node_id, ns in state.node_states.items():
            node_details[node_id] = {
                "status": ns.status.value,
                "attempt": ns.attempt,
                "max_attempts": ns.max_attempts,
                "started_at": ns.started_at.isoformat() if ns.started_at else None,
                "completed_at": ns.completed_at.isoformat() if ns.completed_at else None,
                "error": ns.error_message,
                "worker_id": ns.worker_id,
            }

        return {
            "execution_id": state.execution_id,
            "workflow_name": state.workflow_name,
            "version": state.version,
            "status": state.status.value,
            "is_terminal": state.is_terminal(),
            "created_at": state.created_at.isoformat(),
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "retry_count": state.retry_count,
            "error_message": state.error_message,
            "trace_id": state.trace_id,
            "nodes": node_details,
            "node_count": len(state.node_states),
            "variable_count": len(state.variables),
            "metadata": state.metadata,
        }

    def check_health(self, state: WorkflowState) -> Dict[str, Any]:
        """Run health checks on a workflow state instance."""
        issues = self._consistency.check(state)
        return {
            "execution_id": state.execution_id,
            "healthy": len(issues) == 0,
            "issues": issues,
            "status": state.status.value,
        }

    def execution_summary(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate an execution summary."""
        terminal_count = sum(1 for ns in state.node_states.values() if ns.is_terminal())
        total_nodes = len(state.node_states)
        failed_nodes = [
            nid for nid, ns in state.node_states.items()
            if ns.status.value == "failed"
        ]

        return {
            "execution_id": state.execution_id,
            "status": state.status.value,
            "total_nodes": total_nodes,
            "completed_nodes": terminal_count,
            "pending_nodes": total_nodes - terminal_count,
            "failed_nodes": failed_nodes,
            "failed_count": len(failed_nodes),
            "variables": {k: type(v).__name__ for k, v in state.variables.items()},
            "duration": (
                (state.completed_at - state.started_at).total_seconds()
                if state.completed_at and state.started_at
                else None
            ),
        }
