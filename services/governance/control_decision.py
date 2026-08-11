"""
Control Decision — the decision output of the control plane.

Part 1.5: defines the structured decision the control plane makes
based on triggers, conditions, and control policies.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_state import GovernanceStateType
from .control_action import ControlActionType
from .control_trigger import ControlTrigger, Severity


@dataclass
class ControlDecision:
    """A decision produced by the governance control plane.

    This is NOT a trading decision. It's a governance control decision
    that determines what control actions to take in response to triggers.
    """

    decision_id: str = field(default_factory=lambda: f"CTRL-{uuid.uuid4().hex[:12].upper()}")
    trigger: Optional[ControlTrigger] = None
    current_state: GovernanceStateType = GovernanceStateType.NORMAL
    target_state: GovernanceStateType = GovernanceStateType.NORMAL
    actions: List[ControlActionType] = field(default_factory=list)
    reason: str = ""
    severity: Severity = Severity.INFO
    correlation_id: str = ""
    created_at: float = field(default_factory=time.time)
    actor: str = "control-plane"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Execution tracking
    executed: bool = False
    executed_at: float = 0.0
    execution_result: Optional[Dict[str, Any]] = None

    @property
    def requires_state_change(self) -> bool:
        """Whether this decision changes the governance state."""
        return self.current_state != self.target_state

    @property
    def has_destructive_actions(self) -> bool:
        return any(a.is_destructive for a in self.actions)

    @property
    def is_noop(self) -> bool:
        return len(self.actions) == 0 and not self.requires_state_change

    def add_action(self, action: ControlActionType) -> None:
        if action not in self.actions:
            self.actions.append(action)

    def mark_executed(self, result: Dict[str, Any]) -> None:
        self.executed = True
        self.executed_at = time.time()
        self.execution_result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "trigger_type": self.trigger.trigger_type.name if self.trigger else "",
            "current_state": self.current_state.name,
            "target_state": self.target_state.name,
            "state_change": self.requires_state_change,
            "actions": [a.name for a in self.actions],
            "reason": self.reason,
            "severity": self.severity.name,
            "correlation_id": self.correlation_id,
            "actor": self.actor,
            "executed": self.executed,
            "executed_at": self.executed_at,
            "created_at": self.created_at,
        }

    # ── Factory Methods ──

    @classmethod
    def allow(cls, reason: str = "", correlation_id: str = "") -> "ControlDecision":
        """Create an ALLOW decision — no action needed."""
        return cls(
            target_state=GovernanceStateType.NORMAL,
            actions=[ControlActionType.ALLOW],
            reason=reason or "No governance issues detected.",
            severity=Severity.INFO,
            correlation_id=correlation_id,
        )

    @classmethod
    def warn(
        cls,
        reason: str,
        trigger: Optional[ControlTrigger] = None,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create a WARN decision — annotation only, no restriction."""
        return cls(
            trigger=trigger,
            current_state=GovernanceStateType.NORMAL,
            target_state=GovernanceStateType.WATCH,
            actions=[ControlActionType.WARN],
            reason=reason,
            severity=Severity.LOW,
            correlation_id=correlation_id,
        )

    @classmethod
    def restrict(
        cls,
        reason: str,
        current_state: GovernanceStateType = GovernanceStateType.WATCH,
        trigger: Optional[ControlTrigger] = None,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create a RESTRICT decision."""
        return cls(
            trigger=trigger,
            current_state=current_state,
            target_state=GovernanceStateType.RESTRICTED,
            actions=[ControlActionType.RESTRICT, ControlActionType.REDUCE],
            reason=reason,
            severity=Severity.MEDIUM,
            correlation_id=correlation_id,
        )

    @classmethod
    def freeze(
        cls,
        reason: str,
        current_state: GovernanceStateType = GovernanceStateType.RESTRICTED,
        scope: str = "GLOBAL",
        trigger: Optional[ControlTrigger] = None,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create a FREEZE decision."""
        decision = cls(
            trigger=trigger,
            current_state=current_state,
            target_state=GovernanceStateType.FROZEN,
            actions=[ControlActionType.FREEZE],
            reason=reason,
            severity=Severity.HIGH,
            correlation_id=correlation_id,
        )
        decision.metadata["freeze_scope"] = scope
        return decision

    @classmethod
    def emergency(
        cls,
        reason: str,
        current_state: GovernanceStateType = GovernanceStateType.FROZEN,
        trigger: Optional[ControlTrigger] = None,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create an EMERGENCY decision."""
        return cls(
            trigger=trigger,
            current_state=current_state,
            target_state=GovernanceStateType.EMERGENCY,
            actions=[ControlActionType.EMERGENCY, ControlActionType.FREEZE, ControlActionType.ESCALATE],
            reason=reason,
            severity=Severity.CRITICAL,
            correlation_id=correlation_id,
        )

    @classmethod
    def revoke(
        cls,
        reason: str,
        target: str,
        current_state: GovernanceStateType = GovernanceStateType.NORMAL,
        trigger: Optional[ControlTrigger] = None,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create a REVOKE decision."""
        decision = cls(
            trigger=trigger,
            current_state=current_state,
            target_state=GovernanceStateType.RESTRICTED,
            actions=[ControlActionType.REVOKE, ControlActionType.ESCALATE],
            reason=reason,
            severity=Severity.HIGH,
            correlation_id=correlation_id,
        )
        decision.metadata["revoke_target"] = target
        return decision

    @classmethod
    def recover(
        cls,
        reason: str,
        current_state: GovernanceStateType,
        correlation_id: str = "",
    ) -> "ControlDecision":
        """Create a RECOVERY decision."""
        return cls(
            current_state=current_state,
            target_state=GovernanceStateType.RECOVERY,
            actions=[ControlActionType.RECOVER],
            reason=reason,
            severity=Severity.INFO,
            correlation_id=correlation_id,
        )
