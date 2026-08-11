"""
Control Policy — policies that govern the control plane itself.

Part 1.5: defines the meta-policies that control how the control plane
behaves — mapping triggers → conditions → target states → actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_trigger import TriggerType, Severity
from .control_state import GovernanceStateType
from .control_action import ControlActionType
from .control_condition import ControlCondition, STANDARD_CONTROL_CONDITIONS


@dataclass
class ControlPolicy:
    """A policy that defines control plane behavior.

    Maps triggers through conditions to decide what governance state to
    transition to and what actions to execute.
    """

    policy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True

    # Conditions that this policy evaluates
    conditions: List[ControlCondition] = field(default_factory=list)

    # Default target state and actions
    default_state: GovernanceStateType = GovernanceStateType.NORMAL
    default_actions: List[ControlActionType] = field(default_factory=list)

    # Policy metadata
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(
        self, trigger_type: TriggerType, value: Any, threshold: Any = None
    ) -> Optional[ControlCondition]:
        """Evaluate this policy against a trigger.

        Returns the first matching condition or None.
        """
        if not self.enabled:
            return None

        for condition in sorted(self.conditions, key=lambda c: c.priority, reverse=True):
            if condition.trigger_type == trigger_type and condition.evaluate(value, threshold):
                return condition
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "conditions": [c.to_dict() for c in self.conditions],
            "priority": self.priority,
        }


# ── Standard Control Policies ──

STANDARD_CONTROL_POLICIES: List[ControlPolicy] = [
    ControlPolicy(
        policy_id="CTRL-POL-RISK",
        name="Risk Control Policy",
        description="Controls governance responses to risk breaches.",
        version="1.0.0",
        conditions=[
            c for c in STANDARD_CONTROL_CONDITIONS
            if c.trigger_type.category.name == "RISK"
        ],
        priority=10,
    ),
    ControlPolicy(
        policy_id="CTRL-POL-AUDIT",
        name="Audit Integrity Control Policy",
        description="Controls governance responses to audit failures.",
        version="1.0.0",
        conditions=[
            c for c in STANDARD_CONTROL_CONDITIONS
            if c.trigger_type in (
                TriggerType.AUDIT_INTEGRITY_FAILURE,
                TriggerType.AUDIT_CHAIN_BREAK,
                TriggerType.AUDIT_HASH_MISMATCH,
                TriggerType.AUDIT_COMPLETENESS_FAILURE,
            )
        ],
        priority=20,
    ),
    ControlPolicy(
        policy_id="CTRL-POL-AUTHORITY",
        name="Authority Control Policy",
        description="Controls responses to authority breaches and compromises.",
        version="1.0.0",
        conditions=[
            c for c in STANDARD_CONTROL_CONDITIONS
            if c.trigger_type in (
                TriggerType.AUTHORITY_BREACH,
                TriggerType.AUTHORITY_COMPROMISE,
                TriggerType.AUTHORITY_EXPIRY,
            )
        ],
        priority=15,
    ),
    ControlPolicy(
        policy_id="CTRL-POL-INFRASTRUCTURE",
        name="Infrastructure Control Policy",
        description="Controls responses to infrastructure failures.",
        version="1.0.0",
        conditions=[
            c for c in STANDARD_CONTROL_CONDITIONS
            if c.trigger_type in (
                TriggerType.SERVICE_DEGRADATION,
                TriggerType.DATA_INTEGRITY_FAILURE,
                TriggerType.RISK_ENGINE_UNAVAILABLE,
            )
        ],
        priority=25,
    ),
]
