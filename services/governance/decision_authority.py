"""
Decision Authority — per-actor permission record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .authority_policy import AuthorityLevel


@dataclass
class DecisionAuthority:
    """A single authority grant for an actor + decision type."""

    actor: str
    decision_type: str
    authorized: bool = True

    # Limits
    max_amount: float = float("inf")
    max_risk: float = float("inf")
    scope: str = "GLOBAL"

    # Autonomy
    autonomy_level: AuthorityLevel = AuthorityLevel.RECOMMENDATION
    approval_required: bool = False

    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)

    # Meta
    granted_by: str = "SYSTEM"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "decision_type": self.decision_type,
            "authorized": self.authorized,
            "max_amount": self.max_amount,
            "max_risk": self.max_risk,
            "scope": self.scope,
            "autonomy_level": self.autonomy_level.name,
            "approval_required": self.approval_required,
            "conditions": self.conditions,
            "granted_by": self.granted_by,
            "reason": self.reason,
        }
