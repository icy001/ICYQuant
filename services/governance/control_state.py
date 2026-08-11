"""
Control State — governance system state definitions and state machine.

Part 1.5: defines the governance states (NORMAL → WATCH → RESTRICTED →
FROZEN → EMERGENCY → RECOVERY) and their valid transitions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class GovernanceStateType(Enum):
    """Governance system state enumeration."""

    NORMAL = auto()       # All checks passing, normal operations
    WATCH = auto()        # Mild anomalies detected, monitoring
    RESTRICTED = auto()   # Risk elevated, restrictions applied
    DEGRADED = auto()     # Governance components degraded
    FROZEN = auto()       # New risk frozen, only risk reduction allowed
    EMERGENCY = auto()    # Critical event, emergency actions
    RECOVERY = auto()     # Transitioning back to normal

    @property
    def label(self) -> str:
        labels = {
            GovernanceStateType.NORMAL: "Normal",
            GovernanceStateType.WATCH: "Watch",
            GovernanceStateType.RESTRICTED: "Restricted",
            GovernanceStateType.DEGRADED: "Degraded",
            GovernanceStateType.FROZEN: "Frozen",
            GovernanceStateType.EMERGENCY: "Emergency",
            GovernanceStateType.RECOVERY: "Recovery",
        }
        return labels.get(self, "Unknown")

    @property
    def severity(self) -> int:
        severities = {
            GovernanceStateType.NORMAL: 0,
            GovernanceStateType.WATCH: 1,
            GovernanceStateType.RESTRICTED: 2,
            GovernanceStateType.DEGRADED: 3,
            GovernanceStateType.FROZEN: 4,
            GovernanceStateType.EMERGENCY: 5,
            GovernanceStateType.RECOVERY: 4,
        }
        return severities.get(self, 0)

    @property
    def allows_new_risk(self) -> bool:
        """Whether new risk-taking is allowed in this state."""
        return self in (GovernanceStateType.NORMAL, GovernanceStateType.WATCH)

    @property
    def allows_risk_reduction(self) -> bool:
        """Whether risk reduction is allowed in this state."""
        return True  # Always allow risk reduction

    @property
    def allows_new_orders(self) -> bool:
        return self in (GovernanceStateType.NORMAL, GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED)


# Valid state transitions
VALID_TRANSITIONS: Dict[GovernanceStateType, List[GovernanceStateType]] = {
    GovernanceStateType.NORMAL: [
        GovernanceStateType.WATCH,
        GovernanceStateType.DEGRADED,
    ],
    GovernanceStateType.WATCH: [
        GovernanceStateType.NORMAL,
        GovernanceStateType.RESTRICTED,
        GovernanceStateType.DEGRADED,
    ],
    GovernanceStateType.RESTRICTED: [
        GovernanceStateType.WATCH,
        GovernanceStateType.FROZEN,
        GovernanceStateType.DEGRADED,
        GovernanceStateType.EMERGENCY,
    ],
    GovernanceStateType.DEGRADED: [
        GovernanceStateType.RESTRICTED,
        GovernanceStateType.FROZEN,
        GovernanceStateType.EMERGENCY,
    ],
    GovernanceStateType.FROZEN: [
        GovernanceStateType.RESTRICTED,
        GovernanceStateType.EMERGENCY,
        GovernanceStateType.RECOVERY,
    ],
    GovernanceStateType.EMERGENCY: [
        GovernanceStateType.RECOVERY,
    ],
    GovernanceStateType.RECOVERY: [
        GovernanceStateType.WATCH,
        GovernanceStateType.NORMAL,
    ],
}


@dataclass
class GovernanceStateTransition:
    """Record of a governance state transition."""

    transition_id: str = ""
    from_state: GovernanceStateType = GovernanceStateType.NORMAL
    to_state: GovernanceStateType = GovernanceStateType.NORMAL
    trigger: str = ""           # What triggered the transition
    reason: str = ""            # Detailed reason
    actor: str = ""             # Who/what initiated
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_escalation(self) -> bool:
        return self.to_state.severity > self.from_state.severity

    @property
    def is_deescalation(self) -> bool:
        return self.to_state.severity < self.from_state.severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "from_state": self.from_state.name,
            "to_state": self.to_state.name,
            "trigger": self.trigger,
            "reason": self.reason,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "is_escalation": self.is_escalation,
            "is_deescalation": self.is_deescalation,
        }


class GovernanceStateMachine:
    """Manages governance state and validates transitions."""

    def __init__(self, initial_state: GovernanceStateType = GovernanceStateType.NORMAL):
        self._current_state = initial_state
        self._previous_state: Optional[GovernanceStateType] = None
        self._transitions: List[GovernanceStateTransition] = []
        self._state_history: List[Dict[str, Any]] = []

    @property
    def current_state(self) -> GovernanceStateType:
        return self._current_state

    @property
    def previous_state(self) -> Optional[GovernanceStateType]:
        return self._previous_state

    @property
    def is_normal(self) -> bool:
        return self._current_state == GovernanceStateType.NORMAL

    @property
    def is_elevated(self) -> bool:
        return self._current_state.severity >= GovernanceStateType.RESTRICTED.severity

    @property
    def is_critical(self) -> bool:
        return self._current_state in (GovernanceStateType.EMERGENCY, GovernanceStateType.FROZEN)

    def can_transition(self, target: GovernanceStateType) -> bool:
        """Check if a transition is valid."""
        return target in VALID_TRANSITIONS.get(self._current_state, [])

    def transition(
        self,
        target: GovernanceStateType,
        trigger: str = "",
        reason: str = "",
        actor: str = "",
        correlation_id: str = "",
    ) -> GovernanceStateTransition:
        """Execute a state transition if valid.

        Raises:
            ValueError: if transition is not valid.
        """
        if not self.can_transition(target):
            raise ValueError(
                f"Invalid state transition: {self._current_state.name} → {target.name}"
            )

        import uuid

        t = GovernanceStateTransition(
            transition_id=f"GSTR-{uuid.uuid4().hex[:12].upper()}",
            from_state=self._current_state,
            to_state=target,
            trigger=trigger,
            reason=reason,
            actor=actor,
            correlation_id=correlation_id,
        )

        self._previous_state = self._current_state
        self._current_state = target
        self._transitions.append(t)
        self._state_history.append({
            "from": self._previous_state.name,
            "to": target.name,
            "timestamp": t.timestamp,
            "trigger": trigger,
        })

        return t

    def get_transitions(self, limit: int = 100) -> List[GovernanceStateTransition]:
        return self._transitions[-limit:]

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._state_history[-limit:]

    def time_in_state(self) -> float:
        """Seconds spent in current state."""
        if self._transitions:
            return time.time() - self._transitions[-1].timestamp
        return 0.0

    def summary(self) -> Dict[str, Any]:
        return {
            "current_state": self._current_state.name,
            "severity": self._current_state.severity,
            "allows_new_risk": self._current_state.allows_new_risk,
            "allows_risk_reduction": self._current_state.allows_risk_reduction,
            "total_transitions": len(self._transitions),
            "time_in_state_seconds": self.time_in_state(),
        }
