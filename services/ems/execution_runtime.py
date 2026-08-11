"""Execution Runtime — Async execution task and runtime management.

Provides the ExecutionTask model and runtime lifecycle management for
the EMS execution pipeline.

The runtime manages:
    - Task creation and lifecycle
    - Async event loop coordination
    - Task status tracking

Usage::

    task = ExecutionTask(
        task_id="EXEC_001",
        parent_order_id="PO_001",
        plan=plan,
    )
    task.start()
    task.complete()
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.execution_plan import ExecutionPlan
from services.ems.execution_state import ExecutionStatus


@dataclass
class ExecutionTask:
    """An execution task tracking an active execution.

    Represents one execution run for a parent order. The task goes through
    the full execution lifecycle from PENDING to a terminal state.

    Attributes:
        task_id: Unique task identifier
        parent_order_id: Parent order being executed
        plan: Execution plan driving the execution
        status: Current execution status
        created_at: Task creation time
        started_at: Execution start time
        completed_at: Execution completion time
        error: Error message if status is ERROR
        metadata: Arbitrary task metadata
    """

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_order_id: str = ""
    plan: Optional[ExecutionPlan] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Whether the task is actively executing."""
        return self.status.is_active

    @property
    def is_terminal(self) -> bool:
        """Whether the task has reached a terminal state."""
        return self.status.is_terminal

    @property
    def duration_seconds(self) -> float:
        """Task duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def start(self) -> None:
        """Mark task as started."""
        self.started_at = datetime.now(timezone.utc)
        self.status = ExecutionStatus.SUBMITTING

    def complete(self) -> None:
        """Mark task as completed."""
        self.completed_at = datetime.now(timezone.utc)
        self.status = ExecutionStatus.COMPLETED

    def fail(self, error: str) -> None:
        """Mark task as failed with error.

        Args:
            error: Error message
        """
        self.error = error
        self.completed_at = datetime.now(timezone.utc)
        self.status = ExecutionStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "task_id": self.task_id,
            "parent_order_id": self.parent_order_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
        }
