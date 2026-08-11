"""
Control Condition — conditions evaluated by the control plane.

Part 1.5: defines conditions that map control triggers to governance
state transitions and control actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .control_state import GovernanceStateType
from .control_action import ControlActionType
from .control_trigger import TriggerType, Severity


@dataclass
class ControlCondition:
    """A condition that maps a trigger to a control response.

    Example:
        Condition(
            trigger=TriggerType.DRAWDOWN_BREACH,
            threshold=0.06,
            evaluation="value >= threshold",
            target_state=GovernanceStateType.FROZEN,
            actions=[ControlActionType.FREEZE, ControlActionType.REDUCE],
        )
    """

    condition_id: str = ""
    trigger_type: TriggerType = TriggerType.POLICY_BREACH
    threshold_value: Any = None
    threshold_operator: str = ">="  # >=, >, <=, <, ==, !=
    target_state: GovernanceStateType = GovernanceStateType.NORMAL
    actions: List[ControlActionType] = field(default_factory=list)
    priority: int = 0
    description: str = ""
    enabled: bool = True
    cooldown_seconds: float = 0.0  # Minimum time between firings
    metadata: Dict[str, Any] = field(default_factory=dict)
    _custom_evaluator: Optional[Callable[[Any, Any], bool]] = field(default=None, repr=False)

    def evaluate(self, value: Any, threshold: Any = None) -> bool:
        """Evaluate if the condition is met.

        Args:
            value: The observed value.
            threshold: Override for threshold_value if provided.

        Returns:
            True if the condition triggers.
        """
        if not self.enabled:
            return False

        if self._custom_evaluator:
            try:
                return self._custom_evaluator(value, threshold or self.threshold_value)
            except Exception:
                return False

        thresh = threshold if threshold is not None else self.threshold_value
        if thresh is None:
            return False

        try:
            if isinstance(value, (int, float)) and isinstance(thresh, (int, float)):
                return self._compare_numeric(value, thresh)
        except Exception:
            return False

        return False

    def _compare_numeric(self, value: float, threshold: float) -> bool:
        if self.threshold_operator == ">=":
            return value >= threshold
        elif self.threshold_operator == ">":
            return value > threshold
        elif self.threshold_operator == "<=":
            return value <= threshold
        elif self.threshold_operator == "<":
            return value < threshold
        elif self.threshold_operator == "==":
            return value == threshold
        elif self.threshold_operator == "!=":
            return value != threshold
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "trigger_type": self.trigger_type.name,
            "threshold_value": self.threshold_value,
            "threshold_operator": self.threshold_operator,
            "target_state": self.target_state.name,
            "actions": [a.name for a in self.actions],
            "priority": self.priority,
            "description": self.description,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
        }


# ── Standard conditions ──

STANDARD_CONTROL_CONDITIONS: List[ControlCondition] = [
    # ── Drawdown conditions ──
    ControlCondition(
        condition_id="COND-DD-WATCH",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        threshold_value=0.02,
        threshold_operator=">=",
        target_state=GovernanceStateType.WATCH,
        actions=[ControlActionType.WARN],
        priority=1,
        description="Drawdown >= 2% → WATCH",
    ),
    ControlCondition(
        condition_id="COND-DD-RESTRICT",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        threshold_value=0.04,
        threshold_operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        actions=[ControlActionType.RESTRICT, ControlActionType.REDUCE],
        priority=2,
        description="Drawdown >= 4% → RESTRICTED",
    ),
    ControlCondition(
        condition_id="COND-DD-FREEZE",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        threshold_value=0.06,
        threshold_operator=">=",
        target_state=GovernanceStateType.FROZEN,
        actions=[ControlActionType.FREEZE, ControlActionType.CANCEL],
        priority=3,
        description="Drawdown >= 6% → FROZEN",
    ),
    # ── Stress conditions ──
    ControlCondition(
        condition_id="COND-STRESS-RESTRICT",
        trigger_type=TriggerType.STRESS_BREACH,
        threshold_value=80,
        threshold_operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        actions=[ControlActionType.RESTRICT],
        priority=2,
        description="Stress >= 80 → RESTRICTED",
    ),
    ControlCondition(
        condition_id="COND-STRESS-FREEZE",
        trigger_type=TriggerType.STRESS_BREACH,
        threshold_value=90,
        threshold_operator=">=",
        target_state=GovernanceStateType.FROZEN,
        actions=[ControlActionType.FREEZE],
        priority=3,
        description="Stress >= 90 → FROZEN",
    ),
    # ── Audit conditions ──
    ControlCondition(
        condition_id="COND-AUDIT-EMERGENCY",
        trigger_type=TriggerType.AUDIT_INTEGRITY_FAILURE,
        threshold_value=1,
        threshold_operator=">=",
        target_state=GovernanceStateType.EMERGENCY,
        actions=[ControlActionType.FREEZE, ControlActionType.ESCALATE],
        priority=5,
        description="Audit integrity failure → EMERGENCY",
    ),
    ControlCondition(
        condition_id="COND-AUDIT-CHAIN-DEGRADED",
        trigger_type=TriggerType.AUDIT_CHAIN_BREAK,
        threshold_value=1,
        threshold_operator=">=",
        target_state=GovernanceStateType.DEGRADED,
        actions=[ControlActionType.RESTRICT, ControlActionType.ESCALATE],
        priority=4,
        description="Audit chain break → DEGRADED",
    ),
    # ── Authority conditions ──
    ControlCondition(
        condition_id="COND-AUTH-REVOKE",
        trigger_type=TriggerType.AUTHORITY_COMPROMISE,
        threshold_value=1,
        threshold_operator=">=",
        target_state=GovernanceStateType.EMERGENCY,
        actions=[ControlActionType.REVOKE, ControlActionType.ESCALATE],
        priority=5,
        description="Authority compromise → EMERGENCY + REVOKE",
    ),
    # ── Infrastructure conditions ──
    ControlCondition(
        condition_id="COND-INFRA-DEGRADED",
        trigger_type=TriggerType.RISK_ENGINE_UNAVAILABLE,
        threshold_value=1,
        threshold_operator=">=",
        target_state=GovernanceStateType.DEGRADED,
        actions=[ControlActionType.FREEZE, ControlActionType.ESCALATE],
        priority=4,
        description="Risk engine unavailable → DEGRADED + FREEZE new risk",
    ),
]
