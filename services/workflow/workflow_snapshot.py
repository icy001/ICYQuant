"""Workflow Snapshot — captures a point-in-time state of a workflow execution.

Snapshots are used for:
* Recovery — resume execution from the last saved snapshot after a failure
* Debugging — inspect intermediate states
* Replay — re-execute from a specific point

Each snapshot captures the full execution context including variables, node
results, and execution metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_context import WorkflowContext


@dataclass
class WorkflowSnapshot:
    """A point-in-time capture of workflow execution state.

    Contains everything needed to resume execution from this point:
    the full context (variables, node results, metadata) plus the current
    position in the workflow graph.
    """

    snapshot_id: str
    workflow_id: str
    execution_id: str
    workflow_version: str
    context_data: Dict[str, Any] = field(default_factory=dict)
    current_node: Optional[str] = None
    completed_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    pending_nodes: List[str] = field(default_factory=list)
    status: str = "running"
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def capture(
        cls,
        context: WorkflowContext,
        *,
        workflow_id: str,
        execution_id: str,
        workflow_version: str = "1.0.0",
        current_node: Optional[str] = None,
        completed_nodes: Optional[List[str]] = None,
        failed_nodes: Optional[List[str]] = None,
        pending_nodes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> WorkflowSnapshot:
        """Create a snapshot from the current execution context."""
        return cls(
            snapshot_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            execution_id=execution_id,
            workflow_version=workflow_version,
            context_data=context.snapshot(),
            current_node=current_node,
            completed_nodes=list(completed_nodes or []),
            failed_nodes=list(failed_nodes or []),
            pending_nodes=list(pending_nodes or []),
            status=context.status,
            tags=list(tags or []),
        )

    # ------------------------------------------------------------------
    # Restoration
    # ------------------------------------------------------------------

    def restore_context(self) -> WorkflowContext:
        """Reconstruct a :class:`WorkflowContext` from the snapshot data."""
        return WorkflowContext.from_dict(self.context_data)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def age_seconds(self) -> float:
        """Seconds elapsed since the snapshot was created."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    @property
    def total_nodes(self) -> int:
        return len(self.completed_nodes) + len(self.failed_nodes) + len(self.pending_nodes)

    @property
    def progress_ratio(self) -> float:
        """Ratio of completed nodes to total nodes (0.0 to 1.0)."""
        total = self.total_nodes
        if total == 0:
            return 0.0
        return len(self.completed_nodes) / total

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a plain dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "workflow_version": self.workflow_version,
            "context_data": self.context_data,
            "current_node": self.current_node,
            "completed_nodes": list(self.completed_nodes),
            "failed_nodes": list(self.failed_nodes),
            "pending_nodes": list(self.pending_nodes),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowSnapshot:
        """Reconstruct a snapshot from a serialized dictionary."""
        created_at = data.get("created_at")
        return cls(
            snapshot_id=data["snapshot_id"],
            workflow_id=data["workflow_id"],
            execution_id=data["execution_id"],
            workflow_version=data.get("workflow_version", "1.0.0"),
            context_data=data.get("context_data", {}),
            current_node=data.get("current_node"),
            completed_nodes=list(data.get("completed_nodes", [])),
            failed_nodes=list(data.get("failed_nodes", [])),
            pending_nodes=list(data.get("pending_nodes", [])),
            status=data.get("status", "running"),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
            metadata=dict(data.get("metadata", {})),
            tags=list(data.get("tags", [])),
        )

    def __repr__(self) -> str:
        return (
            f"WorkflowSnapshot(id={self.snapshot_id!r}, "
            f"execution={self.execution_id!r}, "
            f"completed={len(self.completed_nodes)}, "
            f"status={self.status!r})"
        )
