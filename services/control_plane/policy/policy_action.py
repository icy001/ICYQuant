"""
PolicyAction — a standardised operational action the Policy Engine requests.

Actions are *requests*, not executions.  The Policy Engine decides that an
action is needed; the concrete executor (``services.control_plane.actions``)
hands it over to the right subsystem:

    ACTIVATE_KILL_SWITCH   → Kill Switch
    START_RECOVERY         → Recovery Engine
    HALT_TRADING           → Trading Gate / OMS
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from .policy_priority import PolicyPriority


class PolicyActionType(str, Enum):
    """Standardised operational action names."""

    ALLOW_TRADING = "ALLOW_TRADING"
    DEGRADE_TRADING = "DEGRADE_TRADING"
    BLOCK_TRADING = "BLOCK_TRADING"
    HALT_TRADING = "HALT_TRADING"
    ACTIVATE_KILL_SWITCH = "ACTIVATE_KILL_SWITCH"
    START_RECOVERY = "START_RECOVERY"
    ESCALATE_INCIDENT = "ESCALATE_INCIDENT"
    REQUIRE_MANUAL_APPROVAL = "REQUIRE_MANUAL_APPROVAL"


class PolicyAction:
    """A single requested operational action."""

    def __init__(
        self,
        action_type: PolicyActionType,
        target: str = "",
        reason: str = "",
        detail: str = "",
        priority: PolicyPriority = PolicyPriority.MEDIUM,
    ) -> None:
        self.action_type = action_type
        self.target = target
        self.reason = reason
        self.detail = detail
        self.priority = priority

    # -- equality ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PolicyAction):
            return NotImplemented
        return (
            self.action_type == other.action_type
            and self.target == other.target
        )

    def __hash__(self) -> int:
        return hash((self.action_type, self.target))

    def __repr__(self) -> str:
        return (
            f"PolicyAction({self.action_type.value}"
            + (f", target={self.target!r}" if self.target else "")
            + ")"
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "reason": self.reason,
            "detail": self.detail,
            "priority": self.priority.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType(data["action_type"]),
            target=data.get("target", ""),
            reason=data.get("reason", ""),
            detail=data.get("detail", ""),
            priority=PolicyPriority(data.get("priority", PolicyPriority.MEDIUM.value)),
        )
