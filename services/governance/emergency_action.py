"""
Emergency Action — emergency action definitions and execution.

Part 1.5: defines what emergency actions can be taken and records
their execution.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class EmergencyActionType(Enum):
    """Emergency action types."""

    FREEZE_ALL = auto()          # Global new-risk freeze
    FREEZE_STRATEGY = auto()     # Strategy-specific freeze
    CANCEL_ALL_ORDERS = auto()   # Cancel all pending orders
    CANCEL_STRATEGY_ORDERS = auto()
    REDUCE_EXPOSURE = auto()     # Force reduce exposure
    REDUCE_LEVERAGE = auto()     # Force reduce leverage
    REVOKE_AUTHORITY = auto()    # Revoke compromised authority
    REVOKE_ALL_DELEGATIONS = auto()
    ESCALATE = auto()            # Escalate to human operator
    EMERGENCY_CLOSE = auto()     # Emergency position close
    PROTECTIVE_HEDGE = auto()    # Protective hedging

    @property
    def is_risk_reducing(self) -> bool:
        """All emergency actions reduce or contain risk."""
        return self not in (EmergencyActionType.ESCALATE,)

    @property
    def is_destructive(self) -> bool:
        return self in (
            EmergencyActionType.CANCEL_ALL_ORDERS,
            EmergencyActionType.REVOKE_AUTHORITY,
            EmergencyActionType.REVOKE_ALL_DELEGATIONS,
            EmergencyActionType.EMERGENCY_CLOSE,
        )


@dataclass
class EmergencyAction:
    """A recorded emergency action."""

    action_id: str = field(default_factory=lambda: f"EMACT-{uuid.uuid4().hex[:12].upper()}")
    action_type: EmergencyActionType = EmergencyActionType.ESCALATE
    target: str = ""            # What/whom the action targets
    reason: str = ""
    actor: str = "emergency-controller"
    correlation_id: str = ""
    executed: bool = False
    executed_at: float = 0.0
    result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)

    def mark_executed(self, result: Dict[str, Any]) -> None:
        self.executed = True
        self.executed_at = time.time()
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.name,
            "target": self.target,
            "reason": self.reason,
            "actor": self.actor,
            "executed": self.executed,
            "executed_at": self.executed_at,
            "result": self.result,
            "created_at": self.created_at,
        }
