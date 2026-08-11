"""
Emergency Policy — policies governing emergency behavior.

Part 1.5: defines what emergency actions are allowed, their scope,
limits, and safety constraints. Emergency authority is NOT unlimited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .emergency_action import EmergencyActionType


@dataclass
class EmergencyPolicy:
    """Policy that constrains emergency actions.

    Emergency authority must be bounded:
      - Only risk-reducing actions
      - Limited scope and duration
      - Full audit trail
      - No risk increase
    """

    policy_id: str = ""
    name: str = "Default Emergency Policy"
    version: str = "1.0.0"

    # What is allowed
    allowed_actions: List[EmergencyActionType] = field(default_factory=lambda: [
        EmergencyActionType.FREEZE_ALL,
        EmergencyActionType.FREEZE_STRATEGY,
        EmergencyActionType.CANCEL_ALL_ORDERS,
        EmergencyActionType.CANCEL_STRATEGY_ORDERS,
        EmergencyActionType.REDUCE_EXPOSURE,
        EmergencyActionType.REDUCE_LEVERAGE,
        EmergencyActionType.REVOKE_AUTHORITY,
        EmergencyActionType.REVOKE_ALL_DELEGATIONS,
        EmergencyActionType.ESCALATE,
    ])

    # What is EXPLICITLY forbidden during emergency
    forbidden_actions: List[str] = field(default_factory=lambda: [
        "NEW_ALLOCATION",
        "INCREASE_RISK",
        "INCREASE_LEVERAGE",
        "EXPAND_AUTHORITY",
        "GRANT_APPROVAL",
    ])

    # Duration limit for emergency (seconds, 0 = indefinite until manual resolution)
    max_duration_seconds: float = 1800.0  # 30 minutes

    # Require manual confirmation after this many seconds
    require_confirmation_after_seconds: float = 300.0  # 5 minutes

    # Audit requirement
    require_audit: bool = True

    def is_allowed(self, action_type: EmergencyActionType) -> bool:
        """Check if an emergency action is allowed."""
        return action_type in self.allowed_actions

    def is_forbidden_command(self, command: str) -> bool:
        """Check if a command represents a forbidden action."""
        return command in self.forbidden_actions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "version": self.version,
            "allowed_actions": [a.name for a in self.allowed_actions],
            "forbidden_actions": self.forbidden_actions,
            "max_duration_seconds": self.max_duration_seconds,
            "require_confirmation_after_seconds": self.require_confirmation_after_seconds,
        }


# ── Standard Emergency Policy ──

STANDARD_EMERGENCY_POLICY = EmergencyPolicy(
    policy_id="EMPOL-001",
    name="Standard Emergency Policy",
    version="1.0.0",
    allowed_actions=[
        EmergencyActionType.FREEZE_ALL,
        EmergencyActionType.FREEZE_STRATEGY,
        EmergencyActionType.CANCEL_ALL_ORDERS,
        EmergencyActionType.CANCEL_STRATEGY_ORDERS,
        EmergencyActionType.REDUCE_EXPOSURE,
        EmergencyActionType.REDUCE_LEVERAGE,
        EmergencyActionType.REVOKE_AUTHORITY,
        EmergencyActionType.REVOKE_ALL_DELEGATIONS,
        EmergencyActionType.ESCALATE,
    ],
    forbidden_actions=[
        "NEW_ALLOCATION",
        "INCREASE_RISK",
        "INCREASE_LEVERAGE",
        "EXPAND_AUTHORITY",
        "GRANT_APPROVAL",
        "CREATE_DELEGATION",
    ],
)
