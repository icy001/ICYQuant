"""Node state — per-node execution lifecycle and runtime state."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set


class NodeExecutionStatus(str, enum.Enum):
    """Node-level execution status."""

    PENDING = "pending"
    READY = "ready"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

    @classmethod
    def terminal_states(cls) -> Set["NodeExecutionStatus"]:
        return {cls.SUCCESS, cls.FAILED, cls.SKIPPED, cls.CANCELLED}

    @classmethod
    def active_states(cls) -> Set["NodeExecutionStatus"]:
        return {cls.DISPATCHED, cls.RUNNING, cls.RETRYING}

    def is_terminal(self) -> bool:
        return self in self.terminal_states()

    def is_active(self) -> bool:
        return self in self.active_states()


# Valid node state transitions
VALID_NODE_TRANSITIONS: Dict[NodeExecutionStatus, Set[NodeExecutionStatus]] = {
    NodeExecutionStatus.PENDING: {NodeExecutionStatus.READY, NodeExecutionStatus.SKIPPED, NodeExecutionStatus.CANCELLED},
    NodeExecutionStatus.READY: {NodeExecutionStatus.DISPATCHED, NodeExecutionStatus.SKIPPED, NodeExecutionStatus.CANCELLED},
    NodeExecutionStatus.DISPATCHED: {NodeExecutionStatus.RUNNING, NodeExecutionStatus.FAILED, NodeExecutionStatus.CANCELLED},
    NodeExecutionStatus.RUNNING: {
        NodeExecutionStatus.SUCCESS,
        NodeExecutionStatus.FAILED,
        NodeExecutionStatus.TIMEOUT,
        NodeExecutionStatus.RETRYING,
        NodeExecutionStatus.CANCELLED,
    },
    NodeExecutionStatus.RETRYING: {
        NodeExecutionStatus.READY,
        NodeExecutionStatus.FAILED,
        NodeExecutionStatus.CANCELLED,
    },
    NodeExecutionStatus.SUCCESS: set(),
    NodeExecutionStatus.FAILED: set(),
    NodeExecutionStatus.SKIPPED: set(),
    NodeExecutionStatus.TIMEOUT: {NodeExecutionStatus.RETRYING, NodeExecutionStatus.FAILED},
    NodeExecutionStatus.CANCELLED: set(),
}


@dataclass
class NodeState:
    """Mutable runtime state for a single node execution within a workflow.

    Managed independently but belongs to a parent WorkflowState.
    """

    node_id: str = ""
    node_name: str = ""
    node_type: str = ""
    status: NodeExecutionStatus = NodeExecutionStatus.PENDING
    attempt: int = 0
    max_attempts: int = 1
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def is_terminal(self) -> bool:
        return self.status.is_terminal()

    def can_transition_to(self, target: NodeExecutionStatus) -> bool:
        valid = VALID_NODE_TRANSITIONS.get(self.status, set())
        return target in valid

    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "worker_id": self.worker_id,
            "metadata": self.metadata,
        }
