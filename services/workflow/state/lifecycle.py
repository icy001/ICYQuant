"""Workflow lifecycle manager — manages full lifecycle from creation to terminal state."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .workflow_state import WorkflowExecutionStatus, WorkflowState
from .node_state import NodeExecutionStatus

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Central lifecycle orchestrator for workflow instances.

    Responsibilities:
      - Create workflow execution instances
      - Drive top-level state transitions
      - Coordinate node lifecycle callbacks
      - Emit lifecycle events to the event bus
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._event_bus = event_bus
        self._states: Dict[str, WorkflowState] = {}
        self._lifecycle_hooks: Dict[WorkflowExecutionStatus, list] = {
            s: [] for s in WorkflowExecutionStatus
        }

    # ---- Instance creation --------------------------------------------------

    def create_instance(
        self,
        workflow_name: str,
        version: str = "1.0.0",
        variables: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> WorkflowState:
        state = WorkflowState(
            workflow_name=workflow_name,
            version=version,
            variables=variables or {},
            metadata=metadata or {},
            trace_id=trace_id,
        )
        self._states[state.execution_id] = state
        self._emit_event("workflow_created", state.execution_id, state.to_dict())
        logger.info("Workflow instance created: id=%s name=%s", state.execution_id, workflow_name)
        return state

    # ---- Top-level transitions ----------------------------------------------

    async def transition(
        self,
        execution_id: str,
        to_status: WorkflowExecutionStatus,
        reason: Optional[str] = None,
    ) -> bool:
        """Atomically transition a workflow instance to a new status."""
        state = self._states.get(execution_id)
        if state is None:
            raise ValueError(f"Workflow instance not found: {execution_id}")

        if not state.can_transition_to(to_status):
            logger.warning(
                "Invalid transition: %s → %s (execution_id=%s)",
                state.status.value,
                to_status.value,
                execution_id,
            )
            return False

        from_status = state.status
        state.status = to_status
        state.touch()

        if to_status == WorkflowExecutionStatus.RUNNING and state.started_at is None:
            state.started_at = datetime.now(timezone.utc)
        if to_status.is_terminal():
            state.completed_at = datetime.now(timezone.utc)

        # Run hooks
        await self._run_hooks(execution_id, to_status)

        # Emit event
        event_data = {
            "execution_id": execution_id,
            "workflow_name": state.workflow_name,
            "from_status": from_status.value,
            "to_status": to_status.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._emit_event("workflow_status_changed", execution_id, event_data)

        logger.info(
            "Workflow transition: %s %s → %s (reason=%s)",
            execution_id, from_status.value, to_status.value, reason,
        )
        return True

    # ---- Lifecycle hooks ----------------------------------------------------

    def register_hook(
        self, status: WorkflowExecutionStatus, callback: callable
    ) -> None:
        """Register a callback invoked when a workflow reaches the given status."""
        self._lifecycle_hooks[status].append(callback)

    async def _run_hooks(self, execution_id: str, status: WorkflowExecutionStatus) -> None:
        state = self._states.get(execution_id)
        if state is None:
            return
        for hook in self._lifecycle_hooks.get(status, []):
            try:
                if hasattr(hook, "__call__"):
                    result = hook(state)
                    # support both sync and async hooks
                    import inspect
                    if inspect.isawaitable(result):
                        await result
            except Exception:
                logger.exception("Lifecycle hook failed for status=%s", status.value)

    # ---- Queries ------------------------------------------------------------

    def get_state(self, execution_id: str) -> Optional[WorkflowState]:
        return self._states.get(execution_id)

    def get_active_instances(self) -> Dict[str, WorkflowState]:
        return {
            eid: s
            for eid, s in self._states.items()
            if s.status.is_active()
        }

    def remove_instance(self, execution_id: str) -> None:
        self._states.pop(execution_id, None)

    # ---- Internal -----------------------------------------------------------

    def _emit_event(self, event_type: str, key: str, data: Dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, key, data)
            except Exception:
                logger.exception("Failed to emit lifecycle event: %s", event_type)
