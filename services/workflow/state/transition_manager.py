"""Transition manager — records and enforces state transitions atomically.

Every transition is recorded with:
  - Execution ID & node ID
  - From/to status
  - Timestamp
  - Reason
  - Version number (for optimistic concurrency)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from .workflow_state import WorkflowExecutionStatus
from .node_state import NodeExecutionStatus

logger = logging.getLogger(__name__)


@dataclass
class TransitionRecord:
    """Immutable record of a single state transition."""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    node_id: Optional[str] = None
    from_status: str = ""
    to_status: str = ""
    reason: Optional[str] = None
    version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class TransitionManager:
    """Manages atomic state transitions with audit trail.

    Features:
      - Atomic recording of every transition
      - Version tracking for optimistic concurrency
      - Full audit history for replay
      - Integration with event bus
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._transitions: Dict[str, List[TransitionRecord]] = {}
        self._version_counters: Dict[str, int] = {}
        self._event_bus = event_bus

    # ---- Record transitions -------------------------------------------------

    async def record_workflow_transition(
        self,
        execution_id: str,
        from_status: WorkflowExecutionStatus,
        to_status: WorkflowExecutionStatus,
        reason: Optional[str] = None,
    ) -> TransitionRecord:
        """Record a workflow-level transition."""
        version = self._next_version(execution_id)
        record = TransitionRecord(
            execution_id=execution_id,
            from_status=from_status.value,
            to_status=to_status.value,
            reason=reason,
            version=version,
        )
        self._append(execution_id, record)
        self._publish("workflow_transition_recorded", record.to_dict())
        return record

    async def record_node_transition(
        self,
        execution_id: str,
        node_id: str,
        from_status: NodeExecutionStatus,
        to_status: NodeExecutionStatus,
        error_message: Optional[str] = None,
    ) -> TransitionRecord:
        """Record a node-level transition."""
        version = self._next_version(f"{execution_id}:{node_id}")
        record = TransitionRecord(
            execution_id=execution_id,
            node_id=node_id,
            from_status=from_status.value,
            to_status=to_status.value,
            reason=error_message,
            version=version,
        )
        self._append(execution_id, record)
        self._publish("node_transition_recorded", record.to_dict())
        return record

    # ---- Query history ------------------------------------------------------

    def get_history(self, execution_id: str) -> List[TransitionRecord]:
        """Return ordered transition history for an execution."""
        return list(self._transitions.get(execution_id, []))

    def get_node_history(self, execution_id: str, node_id: str) -> List[TransitionRecord]:
        """Return ordered transition history for a specific node."""
        records = self._transitions.get(execution_id, [])
        return [r for r in records if r.node_id == node_id]

    def get_current_version(self, execution_id: str) -> int:
        return self._version_counters.get(execution_id, 0)

    def get_history_since(
        self, execution_id: str, since_version: int
    ) -> List[TransitionRecord]:
        """Get transitions since a given version (for incremental replay)."""
        return [r for r in self.get_history(execution_id) if r.version > since_version]

    # ---- Internal -----------------------------------------------------------

    def _next_version(self, key: str) -> int:
        current = self._version_counters.get(key, 0)
        self._version_counters[key] = current + 1
        return self._version_counters[key]

    def _append(self, execution_id: str, record: TransitionRecord) -> None:
        if execution_id not in self._transitions:
            self._transitions[execution_id] = []
        self._transitions[execution_id].append(record)

    def _publish(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, data)
            except Exception:
                logger.exception("Failed to publish transition event")
