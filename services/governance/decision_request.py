"""
Decision Request — formal request entering the governance pipeline.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class DecisionType(Enum):
    """Types of decisions that require governance oversight."""

    # Capital
    CAPITAL_ALLOCATION = auto()
    CAPITAL_DEALLOCATION = auto()
    CAPITAL_REBALANCE = auto()

    # Portfolio
    PORTFOLIO_CREATE = auto()
    PORTFOLIO_MODIFY = auto()
    PORTFOLIO_CLOSE = auto()

    # Strategy
    STRATEGY_ACTIVATE = auto()
    STRATEGY_DEACTIVATE = auto()
    STRATEGY_MODIFY = auto()

    # Risk
    RISK_BUDGET_CHANGE = auto()
    RISK_LIMIT_CHANGE = auto()
    LEVERAGE_CHANGE = auto()

    # Orders
    ORDER_SUBMIT = auto()
    ORDER_MODIFY = auto()
    ORDER_CANCEL = auto()

    # Execution
    EXECUTION_MODE_CHANGE = auto()

    # Governance
    POLICY_OVERRIDE = auto()
    AUTHORITY_CHANGE = auto()
    CONSTRAINT_WAIVER = auto()
    EMERGENCY_ACTION = auto()


@dataclass
class DecisionRequest:
    """A formal request entering the governance evaluation pipeline."""

    # Core identity
    request_id: str = field(default_factory=lambda: f"DR-{uuid.uuid4().hex[:12]}")
    actor: str = "SYSTEM"
    decision_type: DecisionType = DecisionType.CAPITAL_ALLOCATION

    # Target
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    asset_id: Optional[str] = None

    # Amount / quantity
    requested_amount: Optional[float] = None
    requested_quantity: Optional[float] = None
    requested_leverage: Optional[float] = None

    # Direction
    direction: str = "INCREASE"  # INCREASE / DECREASE / MAINTAIN

    # Scope
    scope: str = "GLOBAL"
    capital_scope: Optional[str] = None

    # Risk
    additional_risk: Optional[float] = None
    post_decision_risk: Optional[float] = None

    # Priority
    priority: int = 0  # Higher = more urgent
    emergency: bool = False

    # Expiry
    expires_at: Optional[float] = None

    # Metadata
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # Routing
    trace_id: Optional[str] = None
    parent_request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "actor": self.actor,
            "decision_type": self.decision_type.name,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "asset_id": self.asset_id,
            "requested_amount": self.requested_amount,
            "requested_quantity": self.requested_quantity,
            "requested_leverage": self.requested_leverage,
            "direction": self.direction,
            "scope": self.scope,
            "capital_scope": self.capital_scope,
            "additional_risk": self.additional_risk,
            "post_decision_risk": self.post_decision_risk,
            "priority": self.priority,
            "emergency": self.emergency,
            "expires_at": self.expires_at,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "parent_request_id": self.parent_request_id,
        }

    @property
    def is_risk_increasing(self) -> bool:
        return self.direction.upper() == "INCREASE"

    @property
    def is_risk_reducing(self) -> bool:
        return self.direction.upper() in ("DECREASE", "REDUCE")
