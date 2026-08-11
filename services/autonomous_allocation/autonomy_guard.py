"""Autonomy Guard — controls what actions are allowed at each autonomy level.

Level 0: Manual — human makes all decisions
Level 1: Recommendation — system suggests, human approves
Level 2: Auto Rebalance — rebalances within approved bands
Level 3: Autonomous Allocation — full autonomous allocation
Level 4: Emergency — risk reduction only, no risk-increasing actions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class AutonomyLevel(str, Enum):
    """Autonomy levels."""
    MANUAL = "MANUAL"        # Level 0
    RECOMMENDATION = "RECOMMENDATION"  # Level 1
    AUTO_REBALANCE = "AUTO_REBALANCE"  # Level 2
    AUTONOMOUS = "AUTONOMOUS"  # Level 3
    EMERGENCY = "EMERGENCY"  # Level 4


class AllowedAction(str, Enum):
    """Actions that can be allowed/denied."""
    ALLOCATE = "ALLOCATE"
    DEALLOCATE = "DEALLOCATE"
    REBALANCE = "REBALANCE"
    FREEZE = "FREEZE"
    UNFREEZE = "UNFREEZE"
    INCREASE_RISK = "INCREASE_RISK"
    DECREASE_RISK = "DECREASE_RISK"
    HEDGE = "HEDGE"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"
    RECOMMEND_ONLY = "RECOMMEND_ONLY"
    ROTATE = "ROTATE"


# Which actions are allowed at each level
LEVEL_ACTIONS: Dict[AutonomyLevel, Set[AllowedAction]] = {
    AutonomyLevel.MANUAL: {
        AllowedAction.RECOMMEND_ONLY,
    },
    AutonomyLevel.RECOMMENDATION: {
        AllowedAction.RECOMMEND_ONLY,
        AllowedAction.REBALANCE,  # With approval
    },
    AutonomyLevel.AUTO_REBALANCE: {
        AllowedAction.REBALANCE,
        AllowedAction.DECREASE_RISK,
        AllowedAction.ROTATE,
    },
    AutonomyLevel.AUTONOMOUS: {
        AllowedAction.ALLOCATE,
        AllowedAction.DEALLOCATE,
        AllowedAction.REBALANCE,
        AllowedAction.INCREASE_RISK,
        AllowedAction.DECREASE_RISK,
        AllowedAction.FREEZE,
        AllowedAction.UNFREEZE,
        AllowedAction.ROTATE,
    },
    AutonomyLevel.EMERGENCY: {
        AllowedAction.DECREASE_RISK,
        AllowedAction.HEDGE,
        AllowedAction.FREEZE,
        AllowedAction.EMERGENCY_EXIT,
    },
}

# Maximum capital change per action at each level
LEVEL_CAPITAL_LIMITS: Dict[AutonomyLevel, Dict[str, float]] = {
    AutonomyLevel.MANUAL: {"max_delta": 0.0},
    AutonomyLevel.RECOMMENDATION: {"max_delta": 0.0},
    AutonomyLevel.AUTO_REBALANCE: {"max_delta": 5_000_000.0, "max_weight_delta": 0.05},
    AutonomyLevel.AUTONOMOUS: {"max_delta": float("inf"), "max_weight_delta": 0.10},
    AutonomyLevel.EMERGENCY: {"max_delta": float("inf"), "emergency_only": True},
}


@dataclass
class AutonomyCheck:
    """Result of an autonomy check."""
    action: AllowedAction
    allowed: bool = True
    requires_approval: bool = False
    capital_limit: float = float("inf")
    reject_reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AutonomyState:
    """Current autonomy state."""
    level: AutonomyLevel = AutonomyLevel.AUTONOMOUS
    level_changed_at: datetime = field(default_factory=datetime.utcnow)
    emergency_triggered_at: Optional[datetime] = None
    actions_taken: int = 0
    actions_blocked: int = 0
    last_action: Optional[str] = None
    last_action_time: Optional[datetime] = None


class AutonomyGuard:
    """Controls what the system can do autonomously.

    Rules:
    - Level 4 (EMERGENCY): ONLY risk-reducing actions allowed
    - Higher levels can always do lower-level actions
    - Each level change is logged
    - Risk-increasing actions at EMERGENCY level are BLOCKED
    """

    def __init__(self, initial_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS):
        self._state = AutonomyState(level=initial_level)

    @property
    def level(self) -> AutonomyLevel:
        return self._state.level

    @property
    def state(self) -> AutonomyState:
        return self._state

    def set_level(self, level: AutonomyLevel) -> None:
        """Change autonomy level with logging."""
        old_level = self._state.level
        self._state.level = level
        self._state.level_changed_at = datetime.utcnow()

        if level == AutonomyLevel.EMERGENCY:
            self._state.emergency_triggered_at = datetime.utcnow()

    def escalate_to_emergency(self, reason: str = "") -> None:
        """Escalate to emergency mode immediately."""
        self.set_level(AutonomyLevel.EMERGENCY)

    def deescalate(self) -> None:
        """Deescalate from emergency to autonomous."""
        if self._state.level == AutonomyLevel.EMERGENCY:
            self.set_level(AutonomyLevel.AUTONOMOUS)

    def check(self, action: AllowedAction,
              capital_delta: float = 0.0) -> AutonomyCheck:
        """Check if an action is allowed at current autonomy level."""
        allowed_actions = LEVEL_ACTIONS.get(self._state.level, set())
        capital_limits = LEVEL_CAPITAL_LIMITS.get(self._state.level, {})

        check = AutonomyCheck(action=action)

        if action not in allowed_actions:
            check.allowed = False
            check.reject_reason = (
                f"Action '{action.value}' not allowed at "
                f"autonomy level '{self._state.level.value}'"
            )
            self._state.actions_blocked += 1
            return check

        # Check capital limits
        max_delta = capital_limits.get("max_delta", float("inf"))
        if abs(capital_delta) > max_delta:
            check.allowed = False
            check.capital_limit = max_delta
            check.reject_reason = (
                f"Capital delta {capital_delta:,.0f} exceeds "
                f"level limit {max_delta:,.0f}"
            )
            self._state.actions_blocked += 1
            return check

        # EMERGENCY: no risk-increasing actions
        if self._state.level == AutonomyLevel.EMERGENCY:
            if action in (AllowedAction.ALLOCATE, AllowedAction.INCREASE_RISK):
                check.allowed = False
                check.reject_reason = "Risk-increasing actions blocked in EMERGENCY mode"
                self._state.actions_blocked += 1
                return check

        # RECOMMENDATION and below require approval for most actions
        if self._state.level in (AutonomyLevel.MANUAL, AutonomyLevel.RECOMMENDATION):
            check.requires_approval = True

        self._state.actions_taken += 1
        self._state.last_action = action.value
        self._state.last_action_time = datetime.utcnow()
        return check

    def check_capital_delta(self, capital_delta: float) -> AutonomyCheck:
        """Convenience: check if a capital change is allowed."""
        action = (AllowedAction.ALLOCATE if capital_delta > 0
                  else AllowedAction.DEALLOCATE if capital_delta < 0
                  else AllowedAction.REBALANCE)
        return self.check(action, capital_delta)

    def reset_stats(self) -> None:
        """Reset action counters."""
        self._state.actions_taken = 0
        self._state.actions_blocked = 0
