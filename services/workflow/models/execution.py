"""Execution instance model.

Represents a single runtime execution of a workflow definition. An
:class:`ExecutionInstance` tracks the input, output, current position,
completed/failed nodes and the lifecycle status of one workflow run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(str, Enum):
    """Lifecycle state of a workflow execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    RETRYING = "RETRYING"

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` when the status represents a finalised state."""
        return self in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMEOUT,
        )


@dataclass
class ExecutionInstance:
    """A single runtime execution of a workflow.

    The instance accumulates progress as nodes are visited (``completed_nodes``,
    ``failed_nodes``, ``current_node``) and stores working data in
    ``variables``. ``checkpoints`` holds identifiers of
    :class:`~services.workflow.models.checkpoint.Checkpoint` records captured
    during the run for recovery purposes.
    """

    execution_id: str
    workflow_id: str
    workflow_version: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    current_node: Optional[str] = None
    completed_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    trace_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checkpoints: List[str] = field(default_factory=list)

    def is_terminal(self) -> bool:
        """Return ``True`` when the execution is in a finalised state."""
        return self.status.is_terminal

    def duration(self) -> Optional[float]:
        """Return the elapsed wall-clock seconds, or ``None`` if not started.

        If the execution has completed, the duration is measured between
        ``started_at`` and ``completed_at``; otherwise it is measured between
        ``started_at`` and the current time.
        """
        if self.started_at is None:
            return None
        end = self.completed_at if self.completed_at is not None else datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the execution to a plain dictionary suitable for JSON encoding."""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status.value,
            "input_data": dict(self.input_data),
            "output_data": dict(self.output_data),
            "variables": dict(self.variables),
            "current_node": self.current_node,
            "completed_nodes": list(self.completed_nodes),
            "failed_nodes": list(self.failed_nodes),
            "error": self.error,
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "checkpoints": list(self.checkpoints),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionInstance:
        """Reconstruct an :class:`ExecutionInstance` from a serialized dictionary."""
        started_at = data.get("started_at")
        completed_at = data.get("completed_at")
        return cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            workflow_version=data["workflow_version"],
            status=ExecutionStatus(data.get("status", ExecutionStatus.PENDING.value)),
            input_data=dict(data.get("input_data", {})),
            output_data=dict(data.get("output_data", {})),
            variables=dict(data.get("variables", {})),
            current_node=data.get("current_node"),
            completed_nodes=list(data.get("completed_nodes", [])),
            failed_nodes=list(data.get("failed_nodes", [])),
            error=data.get("error"),
            trace_id=data.get("trace_id"),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
            checkpoints=list(data.get("checkpoints", [])),
        )


class ExecutionState(str, Enum):
    """Fine-grained execution state for state-machine transitions."""

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    RECOVERING = "RECOVERING"

    @property
    def is_terminal(self) -> bool:
        return self in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        )

    @property
    def is_running(self) -> bool:
        return self in (ExecutionState.RUNNING, ExecutionState.WAITING, ExecutionState.RESUMING)


@dataclass
class ExecutionResult:
    """The final result of a completed workflow execution."""

    execution_id: str
    workflow_id: str
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    output_data: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    completed_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    trace_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED and self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "output_data": dict(self.output_data),
            "node_results": dict(self.node_results),
            "completed_nodes": list(self.completed_nodes),
            "failed_nodes": list(self.failed_nodes),
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionResult:
        started_at = data.get("started_at")
        completed_at = data.get("completed_at")
        return cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            status=ExecutionStatus(data.get("status", "COMPLETED")),
            output_data=dict(data.get("output_data", {})),
            node_results=dict(data.get("node_results", {})),
            completed_nodes=list(data.get("completed_nodes", [])),
            failed_nodes=list(data.get("failed_nodes", [])),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            error=data.get("error"),
            trace_id=data.get("trace_id"),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )
