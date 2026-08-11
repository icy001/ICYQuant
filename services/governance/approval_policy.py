"""
Approval Policy — rules that govern when approval is required and what level.

Connects Part 1.2 Policy Engine effects (REQUIRE_APPROVAL) to the
Part 1.3 Approval Engine, defining approval thresholds per decision type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ApprovalLevel(Enum):
    """What level of approval is needed."""
    AUTONOMOUS = auto()       # No human approval needed
    RISK_MANAGER = auto()     # Single risk manager
    PORTFOLIO_MANAGER = auto()  # Single portfolio manager
    RISK_AND_PORTFOLIO = auto()  # Both risk + portfolio
    INVESTMENT_COMMITTEE = auto()  # Multi-person committee
    INSTITUTIONAL = auto()    # Highest level
    EMERGENCY = auto()        # Emergency override


@dataclass
class ApprovalPolicy:
    """
    Defines what approval is required for a given decision type and amount.

    Example:
        CAPITAL_ALLOCATION:
            0-5M    → AUTONOMOUS
            5-20M   → RISK_MANAGER
            20-50M  → RISK_AND_PORTFOLIO
            >50M    → INVESTMENT_COMMITTEE
    """

    approval_policy_id: str
    name: str
    description: str = ""

    # What decision types this policy covers
    decision_types: List[str] = field(default_factory=list)

    # Threshold rules: [(max_amount, approval_level), ...]
    thresholds: List[ApprovalThresholdRule] = field(default_factory=list)

    # Fallback if no threshold matches
    default_level: ApprovalLevel = ApprovalLevel.AUTONOMOUS

    # Whether this policy is active
    active: bool = True

    # Expiration
    expires_at: Optional[float] = None

    # Meta
    created_by: str = "SYSTEM"
    created_at: float = 0.0
    updated_at: float = 0.0

    def get_level_for(self, decision_type: str, amount: float) -> ApprovalLevel:
        """Resolve approval level for a given decision type and amount."""
        if decision_type not in self.decision_types:
            return self.default_level

        sorted_rules = sorted(self.thresholds, key=lambda r: r.max_amount)
        for rule in sorted_rules:
            if amount <= rule.max_amount:
                return rule.level
        return self.default_level

    def requires_approval(self, decision_type: str, amount: float) -> bool:
        """Check if approval is required (non-autonomous)."""
        return self.get_level_for(decision_type, amount) != ApprovalLevel.AUTONOMOUS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_policy_id": self.approval_policy_id,
            "name": self.name,
            "description": self.description,
            "decision_types": self.decision_types,
            "thresholds": [t.to_dict() for t in self.thresholds],
            "default_level": self.default_level.name,
            "active": self.active,
            "expires_at": self.expires_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ApprovalThresholdRule:
    """A single threshold: amount → approval level."""

    max_amount: float
    level: ApprovalLevel
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_amount": self.max_amount,
            "level": self.level.name,
            "description": self.description,
        }
