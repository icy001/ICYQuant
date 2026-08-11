"""
Decision Trace — full trace of a decision through the governance pipeline.

A DecisionTrace captures every step a decision goes through:
  CREATED → POLICY_CHECK → AUTHORITY_CHECK → APPROVAL → GUARD → EXECUTED
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class TraceStep(Enum):
    """Steps in the governance decision pipeline."""

    SIGNAL = auto()
    STRATEGY = auto()
    DECISION_CREATED = auto()
    RISK_CHECK = auto()
    ALLOCATION_CHECK = auto()
    POLICY_CHECK = auto()
    AUTHORITY_CHECK = auto()
    DELEGATION_CHECK = auto()
    APPROVAL_CHECK = auto()
    APPROVAL_PENDING = auto()
    APPROVAL_GRANTED = auto()
    GUARD_CHECK = auto()
    CERTIFICATE_GENERATED = auto()
    ORDER_CREATED = auto()
    EXECUTION = auto()
    COMPLETED = auto()

    # Failure states
    POLICY_BLOCKED = auto()
    AUTHORITY_DENIED = auto()
    APPROVAL_REJECTED = auto()
    GUARD_BLOCKED = auto()
    EXECUTION_FAILED = auto()


@dataclass
class TraceStepRecord:
    """A single step in the decision trace."""

    step: TraceStep
    status: str = "OK"   # OK, FAILED, SKIPPED, PENDING
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    duration_ms: float = 0.0

    entity_id: str = ""       # e.g. policy_id, approval_id
    entity_type: str = ""     # e.g. "POLICY", "APPROVAL"
    detail: str = ""          # Human-readable detail
    state: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def complete(self, status: str = "OK", detail: str = "") -> None:
        self.status = status
        self.completed_at = time.time()
        self.duration_ms = (self.completed_at - self.started_at) * 1000
        if detail:
            self.detail = detail

    def fail(self, error: str) -> None:
        self.complete(status="FAILED")
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "detail": self.detail,
            "state": self.state,
            "error": self.error,
        }


@dataclass
class DecisionTrace:
    """Full governance trace of a single decision."""

    trace_id: str
    correlation_id: str = ""
    decision_id: str = ""

    # Steps in order
    steps: List[TraceStepRecord] = field(default_factory=list)
    current_step: Optional[TraceStep] = None

    # Results
    final_status: str = "PENDING"
    total_duration_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = f"TRACE-{uuid.uuid4().hex[:12].upper()}"

    def add_step(
        self,
        step: TraceStep,
        entity_id: str = "",
        entity_type: str = "",
        state: Optional[Dict[str, Any]] = None,
    ) -> TraceStepRecord:
        """Add and start a new step."""
        record = TraceStepRecord(
            step=step,
            entity_id=entity_id,
            entity_type=entity_type,
            state=state or {},
        )
        self.steps.append(record)
        self.current_step = step
        return record

    def complete_step(self, status: str = "OK", detail: str = "") -> None:
        """Complete the current step."""
        if self.steps:
            self.steps[-1].complete(status, detail)

    def fail_step(self, error: str) -> None:
        """Mark current step as failed."""
        if self.steps:
            self.steps[-1].fail(error)
            self.final_status = "BLOCKED"

    def complete(self, status: str = "COMPLETED") -> None:
        """Complete the entire trace."""
        self.completed_at = time.time()
        self.total_duration_ms = (self.completed_at - self.started_at) * 1000
        self.final_status = status

    def get_failed_steps(self) -> List[TraceStepRecord]:
        """Get all steps that failed."""
        return [s for s in self.steps if s.status == "FAILED"]

    def get_step_durations(self) -> Dict[str, float]:
        """Get duration of each step."""
        return {s.step.name: s.duration_ms for s in self.steps if s.duration_ms > 0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step.name if self.current_step else None,
            "final_status": self.final_status,
            "total_duration_ms": self.total_duration_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionTrace":
        steps_data = data.get("steps", [])
        steps: List[TraceStepRecord] = []
        for sd in steps_data:
            record = TraceStepRecord(
                step=TraceStep[sd["step"]],
                status=sd.get("status", "OK"),
                started_at=sd.get("started_at", 0),
                completed_at=sd.get("completed_at", 0),
                duration_ms=sd.get("duration_ms", 0),
                entity_id=sd.get("entity_id", ""),
                entity_type=sd.get("entity_type", ""),
                detail=sd.get("detail", ""),
                state=sd.get("state", {}),
                error=sd.get("error", ""),
            )
            steps.append(record)

        current_step = data.get("current_step")
        if current_step:
            current_step = TraceStep[current_step]

        return cls(
            trace_id=data.get("trace_id", ""),
            correlation_id=data.get("correlation_id", ""),
            decision_id=data.get("decision_id", ""),
            steps=steps,
            current_step=current_step,
            final_status=data.get("final_status", "PENDING"),
            total_duration_ms=data.get("total_duration_ms", 0),
            started_at=data.get("started_at", time.time()),
            completed_at=data.get("completed_at", 0),
            metadata=data.get("metadata", {}),
        )
