"""
Approval Stage — groups approval steps into sequential or parallel stages.

A workflow consists of multiple stages; each stage contains one or more steps.
Stages execute in sequence; steps within a stage can execute in parallel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .approval_step import ApprovalStep, StepStatus


class StageType(Enum):
    """Execution mode for steps within a stage."""
    SEQUENTIAL = auto()  # Steps must complete one after another
    PARALLEL = auto()    # Steps can run concurrently
    QUORUM = auto()      # Steps form a voting quorum


class StageStatus(Enum):
    """Overall status of an approval stage."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    CANCELLED = auto()
    SKIPPED = auto()


@dataclass
class ApprovalStage:
    """
    A stage groups approval steps and defines their execution mode.

    Example:
        Stage 1: Risk Review (sequential)
            Step 1.1: Risk Manager review
            Step 1.2: Compliance review

        Stage 2: Portfolio Approval (parallel)
            Step 2.1: Portfolio Manager A
            Step 2.2: Portfolio Manager B

        Stage 3: Institutional Sign-off (quorum)
            Step 3.1-3.5: Committee members (3/5 required)
    """

    stage_id: str
    name: str
    stage_type: StageType = StageType.SEQUENTIAL

    # Steps in this stage
    steps: List[ApprovalStep] = field(default_factory=list)

    # Order
    sequence_order: int = 0

    # Conditions
    required: bool = True
    condition_description: str = ""

    # State
    status: StageStatus = StageStatus.PENDING

    def all_steps_completed(self) -> bool:
        """Check if all required steps in this stage are approved."""
        for step in self.steps:
            if step.required and step.status != StepStatus.APPROVED:
                return False
        return True

    def any_step_rejected(self) -> bool:
        """Check if any step was rejected."""
        return any(s.status == StepStatus.REJECTED for s in self.steps)

    def any_step_expired(self) -> bool:
        """Check if any step expired."""
        return any(s.is_expired() for s in self.steps)

    def get_pending_steps(self) -> List[ApprovalStep]:
        """Get all steps that are still pending."""
        return [s for s in self.steps if s.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS)]

    def get_quorum_approved_count(self) -> int:
        """Count how many steps in a quorum have approved."""
        return sum(1 for s in self.steps if s.status == StepStatus.APPROVED)

    def evaluate_quorum(self) -> bool:
        """Check if quorum is met."""
        if self.stage_type != StageType.QUORUM or not self.steps:
            return False
        first = self.steps[0]
        return self.get_quorum_approved_count() >= first.quorum_minimum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "stage_type": self.stage_type.name,
            "steps": [s.to_dict() for s in self.steps],
            "sequence_order": self.sequence_order,
            "required": self.required,
            "condition_description": self.condition_description,
            "status": self.status.name,
        }
