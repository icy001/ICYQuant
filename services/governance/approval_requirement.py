"""
Approval Requirement — defines when approval is required.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ApprovalLevel(Enum):
    """Levels of approval required."""

    NONE = auto()               # No approval needed
    INTERNAL = auto()           # Internal system approval
    RISK_REVIEW = auto()        # Risk team review
    INSTITUTIONAL = auto()      # Formal institutional approval
    ADMIN = auto()              # Administrator override


@dataclass
class ApprovalRequirement:
    """Defines when approval is required for a decision."""

    requirement_id: str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""

    # When to trigger
    decision_types: List[str] = field(default_factory=list)
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    min_risk: Optional[float] = None
    min_leverage: Optional[float] = None

    # What level of approval
    approval_level: ApprovalLevel = ApprovalLevel.INTERNAL

    # Timeout
    timeout_seconds: float = 3600.0  # 1 hour default

    # Enabled
    enabled: bool = True

    def requires_approval(
        self, request_id: str, decision_type: str,
        amount: Optional[float] = None, risk: Optional[float] = None,
        leverage: Optional[float] = None,
    ) -> bool:
        """Check if this requirement triggers for given parameters."""
        if not self.enabled:
            return False

        # Check decision type
        if self.decision_types and decision_type not in self.decision_types:
            return False

        # Check amount thresholds
        if self.min_amount is not None and amount is not None:
            if amount < self.min_amount:
                return False
        if self.max_amount is not None and amount is not None:
            if amount > self.max_amount:
                return True

        # Check risk
        if self.min_risk is not None and risk is not None:
            if risk < self.min_risk:
                return False

        # Check leverage
        if self.min_leverage is not None and leverage is not None:
            if leverage < self.min_leverage:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "name": self.name,
            "description": self.description,
            "decision_types": self.decision_types,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "min_risk": self.min_risk,
            "min_leverage": self.min_leverage,
            "approval_level": self.approval_level.name,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
        }
