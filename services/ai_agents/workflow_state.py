"""
ICYQuant Workflow State — workflow execution state tracking.

Tracks the runtime state of workflow execution including task status,
intermediate results, error collection, and progress reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowState:
    """Runtime state for an executing workflow."""
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING

    # Task tracking
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # Execution context
    context: dict[str, Any] = field(default_factory=dict)
    task_results: dict[str, Any] = field(default_factory=dict)

    # Error collection
    errors: list[str] = field(default_factory=list)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress_pct(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100.0

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        )

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def get_result(self, task_id: str) -> Optional[Any]:
        """Get the result of a specific task."""
        result = self.task_results.get(task_id)
        if result and isinstance(result, dict):
            return result.get("output")
        return result

    def has_error(self) -> bool:
        return len(self.errors) > 0

    def to_summary(self) -> dict[str, Any]:
        """Get a summary of the workflow state."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "progress": round(self.progress_pct, 1),
            "tasks": f"{self.completed_tasks}/{self.total_tasks}",
            "errors": len(self.errors),
            "duration_seconds": round(self.duration_seconds, 1),
        }
