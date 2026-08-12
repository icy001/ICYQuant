"""
RecoveryStep — a single, self-contained unit of recovery work.

A step is a *coordination* unit, not a state mutator.  It declares what must be
done (``step_type``), tracks its own lifecycle (``status``), records its inputs
and outputs, and may produce :class:`RecoveryAction` requests that downstream
domain services are asked to perform.  The orchestrator never modifies business
state directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .recovery_context import RecoveryContext


class StepType(str, Enum):
    """Kinds of recovery step understood by the orchestrator."""

    ISOLATE_TRADING = "ISOLATE_TRADING"
    FREEZE_STATE = "FREEZE_STATE"
    REPLAY_EVENTS = "REPLAY_EVENTS"
    REBUILD_LEDGER = "REBUILD_LEDGER"
    REBUILD_POSITION = "REBUILD_POSITION"
    RECONCILE_STATE = "RECONCILE_STATE"
    VERIFY_INTEGRITY = "VERIFY_INTEGRITY"
    RESUME_TRADING = "RESUME_TRADING"


class StepStatus(str, Enum):
    """Lifecycle status of a single recovery step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    @property
    def is_terminal(self) -> bool:
        return self in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@dataclass
class RecoveryAction:
    """A request handed to a downstream domain service — nothing is executed
    directly by the recovery engine."""

    action: str
    target: str = ""
    detail: str = ""
    correlation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryAction":
        return cls(
            action=data["action"],
            target=data.get("target", ""),
            detail=data.get("detail", ""),
            correlation_id=data.get("correlation_id", ""),
        )


@dataclass
class StepOutcome:
    """Result of executing one recovery step."""

    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    error_code: str = ""
    actions: List[RecoveryAction] = field(default_factory=list)

    @property
    def error_message(self) -> str:
        return self.error or self.error_code or "STEP_FAILED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": dict(self.output),
            "error": self.error,
            "error_code": self.error_code,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepOutcome":
        return cls(
            success=data["success"],
            output=dict(data.get("output", {})),
            error=data.get("error", ""),
            error_code=data.get("error_code", ""),
            actions=[RecoveryAction.from_dict(a) for a in data.get("actions", [])],
        )


@dataclass
class RecoveryStep:
    """One step of a recovery plan."""

    step_id: str
    step_type: StepType
    status: StepStatus = StepStatus.PENDING
    attempt: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: float = 30.0
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_code: str = ""

    # -- lifecycle --------------------------------------------------------

    def mark_running(self, now: Optional[datetime] = None) -> None:
        self.status = StepStatus.RUNNING
        self.started_at = now or _utcnow()

    def mark_completed(
        self, output: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None
    ) -> None:
        self.status = StepStatus.COMPLETED
        self.completed_at = now or _utcnow()
        if output is not None:
            self.output = dict(output)
        self.error = None
        self.error_code = ""

    def mark_failed(
        self, error: str, now: Optional[datetime] = None, error_code: str = ""
    ) -> None:
        self.status = StepStatus.FAILED
        self.completed_at = now or _utcnow()
        self.error = error
        self.error_code = error_code

    def mark_skipped(self, reason: str = "", now: Optional[datetime] = None) -> None:
        self.status = StepStatus.SKIPPED
        self.completed_at = now or _utcnow()
        if reason:
            self.error = reason

    def reset(self) -> None:
        """Put the step back to PENDING so it can be re-run (retry / resume)."""
        self.status = StepStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.error_code = ""

    # -- predicates -------------------------------------------------------

    @property
    def is_done(self) -> bool:
        return self.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.completed_at or _utcnow()
        return (end - self.started_at).total_seconds()

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": _enum_value(self.step_type),
            "status": _enum_value(self.status),
            "attempt": self.attempt,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "timeout": self.timeout,
            "input": dict(self.input),
            "output": dict(self.output),
            "error": self.error,
            "error_code": self.error_code,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryStep":
        started = data.get("started_at")
        completed = data.get("completed_at")
        return cls(
            step_id=data["step_id"],
            step_type=StepType(data["step_type"]),
            status=StepStatus(data.get("status", "PENDING")),
            attempt=data.get("attempt", 0),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            timeout=data.get("timeout", 30.0),
            input=dict(data.get("input", {})),
            output=dict(data.get("output", {})),
            error=data.get("error"),
            error_code=data.get("error_code", ""),
        )


def make_step(
    step_type: StepType,
    step_id: Optional[str] = None,
    **input_: Any,
) -> RecoveryStep:
    """Convenience factory — ``step_id`` defaults to the step type name."""
    return RecoveryStep(
        step_id=step_id or step_type.value,
        step_type=step_type,
        input=dict(input_),
    )


__all__ = [
    "StepType",
    "StepStatus",
    "RecoveryStep",
    "RecoveryAction",
    "StepOutcome",
    "make_step",
    "RecoveryContext",
]
