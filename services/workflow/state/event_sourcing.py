"""Event sourcing — rebuild workflow state from event history.

Execution model: Events → Replay → Rebuild State
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .workflow_state import WorkflowExecutionStatus, WorkflowState
from .node_state import NodeExecutionStatus, NodeState
from .event_store import EventStore, StoredEvent
from .journal import Journal, JournalEntryType

logger = logging.getLogger(__name__)


class EventSourcingEngine:
    """Rebuilds workflow state by replaying stored events.

    The event stream is the single source of truth. State is a projection
    of events, and can always be rebuilt from scratch or incrementally.
    """

    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        journal: Optional[Journal] = None,
    ):
        self._event_store = event_store or EventStore()
        self._journal = journal or Journal()

    # ---- Full state rebuild -------------------------------------------------

    async def rebuild_state(self, execution_id: str) -> Optional[WorkflowState]:
        """Rebuild complete workflow state from all events for an execution."""
        events = await self._event_store.get_events(execution_id)
        if not events:
            return None

        state = self._create_empty_state(execution_id)
        await self._apply_events(state, events)
        return state

    async def rebuild_from_journal(self, execution_id: str) -> Optional[WorkflowState]:
        """Rebuild state from journal entries."""
        entries = await self._journal.get_entries(execution_id)
        if not entries:
            return None

        state = self._create_empty_state(execution_id)
        for entry in entries:
            self._apply_journal_entry(state, entry)
        return state

    async def incremental_rebuild(
        self,
        state: WorkflowState,
        since_version: int,
    ) -> WorkflowState:
        """Apply only events since a given version to an existing state."""
        events = await self._event_store.get_events(
            state.execution_id, since_version=since_version
        )
        await self._apply_events(state, events)
        return state

    # ---- Audit / Debug ------------------------------------------------------

    async def get_state_at_time(
        self, execution_id: str, until: datetime
    ) -> Optional[WorkflowState]:
        """Rebuild state as it was at a specific point in time."""
        events = await self._event_store.get_events(execution_id)
        past_events = [e for e in events if e.timestamp <= until]
        if not past_events:
            return None

        state = self._create_empty_state(execution_id)
        await self._apply_events(state, past_events)
        return state

    async def get_state_before_event(
        self, execution_id: str, event_id: str
    ) -> Optional[WorkflowState]:
        """Rebuild state just before a specific event."""
        events = await self._event_store.get_events(execution_id)
        idx = next((i for i, e in enumerate(events) if e.event_id == event_id), None)
        if idx is None:
            return None

        state = self._create_empty_state(execution_id)
        await self._apply_events(state, events[:idx])
        return state

    # ---- Internal -----------------------------------------------------------

    def _create_empty_state(self, execution_id: str) -> WorkflowState:
        return WorkflowState(execution_id=execution_id)

    async def _apply_events(
        self, state: WorkflowState, events: List[StoredEvent]
    ) -> None:
        for event in events:
            self._apply_event(state, event)

    def _apply_event(self, state: WorkflowState, event: StoredEvent) -> None:
        event_type = event.event_type
        payload = event.payload

        if event_type == "workflow_state_changed":
            to_status = payload.get("to")
            if to_status:
                state.status = WorkflowExecutionStatus(to_status)

        elif event_type == "node_state_changed":
            node_id = payload.get("node_id")
            to_status = payload.get("to")
            if node_id and to_status:
                if node_id not in state.node_states:
                    state.node_states[node_id] = NodeState(node_id=node_id)
                state.node_states[node_id].status = NodeExecutionStatus(to_status)
                if "error" in payload:
                    state.node_states[node_id].error_message = payload["error"]

        elif event_type == "workflow_created":
            state.workflow_name = payload.get("workflow_name", state.workflow_name)
            state.version = payload.get("version", state.version)
            state.trace_id = payload.get("trace_id", state.trace_id)

        state.touch()

    def _apply_journal_entry(self, state: WorkflowState, entry: Any) -> None:
        entry_type = entry.entry_type if hasattr(entry, 'entry_type') else JournalEntryType(entry.get("entry_type", ""))

        status_map = {
            JournalEntryType.WORKFLOW_STARTED: WorkflowExecutionStatus.RUNNING,
            JournalEntryType.WORKFLOW_SUSPENDED: WorkflowExecutionStatus.SUSPENDED,
            JournalEntryType.WORKFLOW_RESUMED: WorkflowExecutionStatus.RUNNING,
            JournalEntryType.WORKFLOW_COMPLETED: WorkflowExecutionStatus.COMPLETED,
            JournalEntryType.WORKFLOW_FAILED: WorkflowExecutionStatus.FAILED,
            JournalEntryType.WORKFLOW_CANCELLED: WorkflowExecutionStatus.CANCELLED,
            JournalEntryType.WORKFLOW_TIMEOUT: WorkflowExecutionStatus.TIMEOUT,
        }

        if entry_type in status_map:
            state.status = status_map[entry_type]
        state.touch()
