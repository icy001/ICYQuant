"""RecoveryJob and RecoveryResult — for Part 1.5 recovery manager."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .recovery_state import RecoveryState


@dataclass
class RecoveryJob:
    """A single recovery job for an order.

    Each recovery has a unique recovery_id for idempotency.
    Multiple attempts are tracked within a single job.
    """

    recovery_id: str = field(
        default_factory=lambda: f"REC-{__import__('uuid').uuid4().hex[:8].upper()}"
    )
    order_id: str = ""
    trigger: str = ""  # ACK_TIMEOUT, SUBMISSION_TIMEOUT, etc.

    state: RecoveryState = RecoveryState.PENDING
    attempt: int = 0
    max_attempts: int = 3

    created_at: float = field(default_factory=lambda: __import__("time").time())
    started_at: float = 0.0
    completed_at: float = 0.0

    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    @property
    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts and not self.is_terminal

    def start(self) -> None:
        self.state = RecoveryState.RUNNING
        self.started_at = time.time()

    def record_attempt(self) -> None:
        self.attempt += 1

    def mark_recovered(self, result: Dict[str, Any]) -> None:
        self.state = RecoveryState.RECOVERED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str = "") -> None:
        self.state = RecoveryState.FAILED
        self.error = error
        self.completed_at = time.time()

    def mark_escalated(self, reason: str = "") -> None:
        self.state = RecoveryState.ESCALATED
        self.error = reason
        self.completed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "order_id": self.order_id,
            "trigger": self.trigger,
            "state": self.state.name,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": dict(self.result),
            "error": self.error,
        }
