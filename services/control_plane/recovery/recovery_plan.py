"""
RecoveryPlan — an ordered, deterministic sequence of recovery steps.

Recovery is never "try a random fix"; it is always a plan.  A plan knows its
own progress, which step comes next, and how to resume from a checkpoint after
a crash or retry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .recovery_checkpoint import RecoveryCheckpoint
from .recovery_step import RecoveryStep, StepStatus


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@dataclass
class RecoveryPlan:
    """An ordered list of steps for one recovery session."""

    recovery_id: str
    steps: List[RecoveryStep] = field(default_factory=list)

    # -- building ---------------------------------------------------------

    def add_step(self, step: RecoveryStep) -> "RecoveryPlan":
        self.steps.append(step)
        return self

    def with_steps(self, *steps: RecoveryStep) -> "RecoveryPlan":
        self.steps.extend(steps)
        return self

    # -- navigation -------------------------------------------------------

    def current_step(self) -> Optional[RecoveryStep]:
        """First step that still needs to run (PENDING / RUNNING)."""
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                return step
        return None

    def next_step(self) -> Optional[RecoveryStep]:
        """First step after the current one."""
        current = self.current_step()
        if current is None:
            return None
        index = self.steps.index(current)
        for step in self.steps[index + 1:]:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                return step
        return None

    def failed_step(self) -> Optional[RecoveryStep]:
        for step in self.steps:
            if step.status is StepStatus.FAILED:
                return step
        return None

    def step(self, step_id: str) -> Optional[RecoveryStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    # -- progress ---------------------------------------------------------

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.is_done)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status is StepStatus.FAILED)

    def progress(self) -> float:
        """Fraction of steps completed, in [0.0, 1.0]."""
        if not self.steps:
            return 0.0
        return self.completed_count / len(self.steps)

    def is_complete(self) -> bool:
        return bool(self.steps) and all(s.is_done for s in self.steps)

    def is_failed(self) -> bool:
        return any(s.status is StepStatus.FAILED for s in self.steps)

    # -- resumption -------------------------------------------------------

    def resume_from(self, checkpoint: RecoveryCheckpoint) -> bool:
        """Prepare the plan to continue from a checkpoint.

        Steps up to (and including) the checkpoint's step are considered done;
        any step *after* it that was left RUNNING / FAILED is reset so the
        orchestrator re-runs it.  Returns whether the checkpoint step was found.
        """
        found = False
        for step in self.steps:
            if not found:
                if step.step_id == checkpoint.step_id:
                    found = True
                continue
            if step.status in (StepStatus.RUNNING, StepStatus.FAILED):
                step.reset()
        if checkpoint.payload and found:
            for step in self.steps:
                if not step.is_done:
                    step.input = {**checkpoint.payload, **step.input}
                    break
        return found

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryPlan":
        return cls(
            recovery_id=data["recovery_id"],
            steps=[RecoveryStep.from_dict(s) for s in data.get("steps", [])],
        )


__all__ = ["RecoveryPlan"]
