"""Runtime State — state machine and status tracking for research runtimes.

Tracks lifecycle transitions, execution phases, and error states
for each research runtime environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RuntimeStatus(str, Enum):
    """Runtime lifecycle status."""

    PENDING = "pending"           # Awaiting provisioning
    PROVISIONING = "provisioning" # Environment being created
    READY = "ready"               # Ready to execute
    RUNNING = "running"           # Actively executing
    PAUSED = "paused"             # Execution paused
    COLLECTING = "collecting"     # Gathering results
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"             # Execution failed
    CANCELLED = "cancelled"       # User cancelled
    TIMED_OUT = "timed_out"       # Execution exceeded timeout
    TEARING_DOWN = "tearing_down" # Environment cleanup
    TERMINATED = "terminated"     # Fully terminated


# Valid status transitions
_transitions: Dict[RuntimeStatus, List[RuntimeStatus]] = {
    RuntimeStatus.PENDING: [RuntimeStatus.PROVISIONING, RuntimeStatus.CANCELLED],
    RuntimeStatus.PROVISIONING: [RuntimeStatus.READY, RuntimeStatus.FAILED, RuntimeStatus.CANCELLED],
    RuntimeStatus.READY: [RuntimeStatus.RUNNING, RuntimeStatus.CANCELLED, RuntimeStatus.TEARING_DOWN],
    RuntimeStatus.RUNNING: [RuntimeStatus.PAUSED, RuntimeStatus.COLLECTING,
                             RuntimeStatus.FAILED, RuntimeStatus.CANCELLED, RuntimeStatus.TIMED_OUT],
    RuntimeStatus.PAUSED: [RuntimeStatus.RUNNING, RuntimeStatus.CANCELLED],
    RuntimeStatus.COLLECTING: [RuntimeStatus.COMPLETED, RuntimeStatus.FAILED],
    RuntimeStatus.COMPLETED: [RuntimeStatus.TEARING_DOWN],
    RuntimeStatus.FAILED: [RuntimeStatus.TEARING_DOWN],
    RuntimeStatus.CANCELLED: [RuntimeStatus.TEARING_DOWN],
    RuntimeStatus.TIMED_OUT: [RuntimeStatus.TEARING_DOWN],
    RuntimeStatus.TEARING_DOWN: [RuntimeStatus.TERMINATED],
    RuntimeStatus.TERMINATED: [],
}


@dataclass
class RuntimeState:
    """Tracks the current state and history of a runtime environment.

    Implements a state machine with validated transitions between
    lifecycle states, maintaining full history for audit/debug.
    """

    env_id: str = ""
    experiment_id: str = ""
    status: RuntimeStatus = RuntimeStatus.PENDING
    phase: str = ""
    progress: float = 0.0          # 0.0 - 1.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    retry_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Whether the runtime has reached a terminal state."""
        return self.status in {
            RuntimeStatus.COMPLETED, RuntimeStatus.FAILED,
            RuntimeStatus.CANCELLED, RuntimeStatus.TIMED_OUT,
            RuntimeStatus.TERMINATED,
        }

    @property
    def is_active(self) -> bool:
        """Whether the runtime is actively processing."""
        return self.status in {
            RuntimeStatus.PROVISIONING, RuntimeStatus.READY,
            RuntimeStatus.RUNNING, RuntimeStatus.COLLECTING,
        }

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def transition(self, new_status: RuntimeStatus, reason: str = "") -> bool:
        """Attempt a state transition. Returns True if valid and applied."""
        if new_status not in _transitions.get(self.status, []):
            return False
        previous = self.status
        self.status = new_status
        self.history.append({
            "from": previous.value,
            "to": new_status.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if previous == RuntimeStatus.PENDING and new_status == RuntimeStatus.PROVISIONING:
            self.started_at = datetime.now(timezone.utc)
        if new_status in (RuntimeStatus.COMPLETED, RuntimeStatus.FAILED):
            self.completed_at = datetime.now(timezone.utc)
        return True

    def complete(self) -> None:
        self.transition(RuntimeStatus.COLLECTING)
        self.transition(RuntimeStatus.COMPLETED)

    def fail(self, error: str, error_type: str = "RuntimeError") -> None:
        self.error_message = error
        self.error_type = error_type
        self.transition(RuntimeStatus.FAILED, reason=error)

    def cancel(self) -> None:
        self.transition(RuntimeStatus.CANCELLED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env_id": self.env_id,
            "experiment_id": self.experiment_id,
            "status": self.status.value,
            "phase": self.phase,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "elapsed_seconds": self.elapsed_seconds,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "retry_count": self.retry_count,
            "is_terminal": self.is_terminal,
            "is_active": self.is_active,
            "history": self.history,
        }

    def __repr__(self) -> str:
        return (
            f"RuntimeState(env={self.env_id[:8]}, "
            f"status={self.status.value}, progress={self.progress:.0%})"
        )
