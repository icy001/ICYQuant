"""Allocation Action — executable actions and autonomy levels.

Defines what actions the system can take and at what level
of autonomy it operates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional


class AutonomyLevel(IntEnum):
    """Autonomy levels for the allocation system.

    LEVEL 0: Manual — human makes all decisions
    LEVEL 1: Recommendation — system suggests, human approves
    LEVEL 2: Auto Rebalance — system rebalances within approved bands
    LEVEL 3: Autonomous Allocation — system allocates freely
    LEVEL 4: Emergency Autonomous Risk Control — system reduces risk only
    """
    MANUAL = 0
    RECOMMENDATION = 1
    AUTO_REBALANCE = 2
    AUTONOMOUS = 3
    EMERGENCY = 4


class ActionType(str, Enum):
    """Type of executable action."""
    ALLOCATE = "ALLOCATE"
    DEALLOCATE = "DEALLOCATE"
    REBALANCE = "REBALANCE"
    HOLD = "HOLD"
    FREEZE = "FREEZE"
    LIQUIDATE = "LIQUIDATE"
    HEDGE = "HEDGE"
    INCREASE_RESERVE = "INCREASE_RESERVE"
    DECREASE_RESERVE = "DECREASE_RESERVE"
    REDUCE_RISK = "REDUCE_RISK"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"
    ROTATE = "ROTATE"
    NONE = "NONE"


# Actions allowed at each autonomy level
AUTONOMY_ACTION_MAP: Dict[AutonomyLevel, List[ActionType]] = {
    AutonomyLevel.MANUAL: [ActionType.NONE],
    AutonomyLevel.RECOMMENDATION: [
        ActionType.ALLOCATE, ActionType.DEALLOCATE, ActionType.REBALANCE,
        ActionType.HOLD, ActionType.ROTATE,
    ],
    AutonomyLevel.AUTO_REBALANCE: [
        ActionType.ALLOCATE, ActionType.DEALLOCATE, ActionType.REBALANCE,
        ActionType.HOLD, ActionType.ROTATE,
        ActionType.INCREASE_RESERVE, ActionType.DECREASE_RESERVE,
    ],
    AutonomyLevel.AUTONOMOUS: [
        ActionType.ALLOCATE, ActionType.DEALLOCATE, ActionType.REBALANCE,
        ActionType.HOLD, ActionType.FREEZE, ActionType.ROTATE,
        ActionType.INCREASE_RESERVE, ActionType.DECREASE_RESERVE,
        ActionType.REDUCE_RISK,
    ],
    AutonomyLevel.EMERGENCY: [
        ActionType.REDUCE_RISK, ActionType.HEDGE, ActionType.FREEZE,
        ActionType.EMERGENCY_EXIT, ActionType.LIQUIDATE,
        ActionType.INCREASE_RESERVE,
    ],
}


class ActionUrgency(str, Enum):
    """Urgency level of an action."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AllocationAction:
    """An executable allocation action."""

    action_type: ActionType
    strategy_id: str = ""
    urgency: ActionUrgency = ActionUrgency.NORMAL
    autonomy_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS

    # Action parameters
    capital_delta: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0
    target_capital: float = 0.0
    current_capital: float = 0.0

    # Constraints
    max_order_size: float = 0.0
    min_order_size: float = 0.0
    max_participation: float = 0.10

    # Context
    reason: str = ""
    score_improvement: float = 0.0
    risk_impact: float = 0.0
    expected_cost: float = 0.0

    # Meta
    action_id: str = ""
    parent_decision_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.action_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.action_id = f"act-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"

    @classmethod
    def is_allowed(cls, autonomy_level: AutonomyLevel,
                   action_type: ActionType) -> bool:
        """Check if an action is allowed at a given autonomy level."""
        allowed = AUTONOMY_ACTION_MAP.get(autonomy_level, [ActionType.NONE])
        return action_type in allowed

    @property
    def is_risk_reducing(self) -> bool:
        """Check if this action reduces risk."""
        return self.action_type in (
            ActionType.DEALLOCATE, ActionType.REDUCE_RISK,
            ActionType.EMERGENCY_EXIT, ActionType.LIQUIDATE,
            ActionType.HEDGE, ActionType.FREEZE,
            ActionType.INCREASE_RESERVE,
        )

    @property
    def is_risk_increasing(self) -> bool:
        """Check if this action increases risk (not allowed in EMERGENCY)."""
        return self.action_type in (
            ActionType.ALLOCATE, ActionType.DECREASE_RESERVE,
        )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def validate(self) -> List[str]:
        """Validate this action against its autonomy level."""
        errors = []

        if not self.is_allowed(self.autonomy_level, self.action_type):
            errors.append(
                f"Action {self.action_type.value} not allowed at "
                f"autonomy level {self.autonomy_level.name}"
            )

        if self.autonomy_level == AutonomyLevel.EMERGENCY and self.is_risk_increasing:
            errors.append(
                f"Risk-increasing action {self.action_type.value} not allowed "
                f"at EMERGENCY autonomy level"
            )

        if self.is_expired:
            errors.append(f"Action expired at {self.expires_at}")

        if self.max_order_size > 0 and abs(self.capital_delta) > self.max_order_size:
            errors.append(
                f"Capital delta {self.capital_delta:,.0f} exceeds max order size {self.max_order_size:,.0f}"
            )

        return errors

    def summarize(self) -> str:
        """Generate a human-readable action summary."""
        return (
            f"AllocationAction[{self.action_id}] {self.action_type.value} "
            f"({self.urgency.value}) {self.strategy_id}: "
            f"{self.current_capital:,.0f}→{self.target_capital:,.0f} "
            f"[{self.autonomy_level.name}]"
        )
