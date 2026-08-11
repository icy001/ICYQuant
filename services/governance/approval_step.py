"""
Approval Step — a single approval step within an approval workflow.

Each step defines:
  - Which approver/role is required
  - What authority level is needed
  - Whether it's required or optional
  - Any conditions or timeouts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class StepType(Enum):
    """Type of approval step."""
    REVIEW = auto()     # Review by a specific role
    APPROVE = auto()    # Formal approval
    ACKNOWLEDGE = auto()  # Acknowledgment only
    QUORUM = auto()     # Multi-person vote
    CONDITIONAL = auto()  # Conditional on some factor


class StepStatus(Enum):
    """Status of an individual approval step."""
    PENDING = auto()
    IN_PROGRESS = auto()
    APPROVED = auto()
    REJECTED = auto()
    SKIPPED = auto()
    EXPIRED = auto()
    CANCELLED = auto()


@dataclass
class ApprovalStep:
    """
    A single step in a multi-step approval workflow.

    Example:
        Step 1: Risk Manager review (required, 15 min timeout)
        Step 2: Portfolio Manager approval (required, 30 min timeout)
        Step 3: Institutional sign-off if > 50M (conditional)
    """

    step_id: str
    name: str
    step_type: StepType = StepType.APPROVE

    # Who
    required_role: str = ""
    required_authority_level: str = ""

    # How
    required: bool = True
    timeout_seconds: float = 1800.0  # 30 minutes default

    # Quorum settings
    quorum_minimum: int = 1
    quorum_total: int = 1
    quorum_mode: str = "ALL"  # ALL, ANY, MAJORITY

    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)
    condition_description: str = ""

    # Order
    sequence_order: int = 0

    # State
    status: StepStatus = StepStatus.PENDING

    # Execution
    assigned_approver: str = ""
    assigned_delegation_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    comment: str = ""

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if the step has timed out."""
        import time
        if self.status not in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
            return False
        if self.started_at <= 0:
            return False
        now = current_time or time.time()
        return (now - self.started_at) > self.timeout_seconds

    def can_proceed(self) -> bool:
        """Check if the workflow can proceed past this step."""
        if not self.required and self.status in (StepStatus.SKIPPED,):
            return True
        return self.status == StepStatus.APPROVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "step_type": self.step_type.name,
            "required_role": self.required_role,
            "required_authority_level": self.required_authority_level,
            "required": self.required,
            "timeout_seconds": self.timeout_seconds,
            "quorum_minimum": self.quorum_minimum,
            "quorum_total": self.quorum_total,
            "quorum_mode": self.quorum_mode,
            "condition_description": self.condition_description,
            "sequence_order": self.sequence_order,
            "status": self.status.name,
            "assigned_approver": self.assigned_approver,
            "assigned_delegation_id": self.assigned_delegation_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "comment": self.comment,
        }
