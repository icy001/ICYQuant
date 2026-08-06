"""Workflow persistent state — enumerates all workflow-level lifecycle states.

States follow a strict DAG: CREATED → VALIDATED → READY → RUNNING → {COMPLETED, FAILED, CANCELLED, TIMEOUT}.
SUSPENDED and WAITING are transient sub-states reachable from RUNNING.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


class WorkflowExecutionStatus(str, enum.Enum):
    """Workflow-level execution status."""

    CREATED = "created"
    VALIDATED = "validated"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

    @classmethod
    def terminal_states(cls) -> set["WorkflowExecutionStatus"]:
        return {cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.TIMEOUT}

    @classmethod
    def active_states(cls) -> set["WorkflowExecutionStatus"]:
        return {cls.RUNNING, cls.WAITING, cls.SUSPENDED}

    @classmethod
    def resumable_states(cls) -> set["WorkflowExecutionStatus"]:
        return {cls.SUSPENDED, cls.WAITING, cls.RUNNING}

    def is_terminal(self) -> bool:
        return self in self.terminal_states()

    def is_active(self) -> bool:
        return self in self.active_states()


# Valid transitions map
VALID_WORKFLOW_TRANSITIONS: Dict[WorkflowExecutionStatus, set[WorkflowExecutionStatus]] = {
    WorkflowExecutionStatus.CREATED: {WorkflowExecutionStatus.VALIDATED, WorkflowExecutionStatus.CANCELLED},
    WorkflowExecutionStatus.VALIDATED: {WorkflowExecutionStatus.READY, WorkflowExecutionStatus.CANCELLED},
    WorkflowExecutionStatus.READY: {WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.CANCELLED},
    WorkflowExecutionStatus.RUNNING: {
        WorkflowExecutionStatus.WAITING,
        WorkflowExecutionStatus.SUSPENDED,
        WorkflowExecutionStatus.COMPLETED,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELLED,
        WorkflowExecutionStatus.TIMEOUT,
    },
    WorkflowExecutionStatus.WAITING: {
        WorkflowExecutionStatus.RUNNING,
        WorkflowExecutionStatus.SUSPENDED,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELLED,
        WorkflowExecutionStatus.TIMEOUT,
    },
    WorkflowExecutionStatus.SUSPENDED: {
        WorkflowExecutionStatus.RUNNING,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELLED,
    },
    WorkflowExecutionStatus.COMPLETED: set(),
    WorkflowExecutionStatus.FAILED: set(),
    WorkflowExecutionStatus.CANCELLED: set(),
    WorkflowExecutionStatus.TIMEOUT: set(),
}


@dataclass
class WorkflowState:
    """Mutable runtime state for a single workflow execution instance.

    This state is persisted via checkpoint / snapshot and restored on recovery.
    """

    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    version: str = "1.0.0"
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.CREATED
    node_states: Dict[str, "NodeState"] = field(default_factory=dict)  # type: ignore[name-defined]
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def is_terminal(self) -> bool:
        return self.status.is_terminal()

    def can_transition_to(self, target: WorkflowExecutionStatus) -> bool:
        valid = VALID_WORKFLOW_TRANSITIONS.get(self.status, set())
        return target in valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
            "version": self.version,
            "status": self.status.value,
            "node_states": {k: v.to_dict() for k, v in self.node_states.items()},
            "variables": self.variables,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
            "parent_execution_id": self.parent_execution_id,
            "metadata": self.metadata,
            "tags": self.tags,
        }


# Forward reference resolved at bottom to avoid circular import
