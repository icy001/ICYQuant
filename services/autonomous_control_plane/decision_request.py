"""
Decision Request — Standardized request format for autonomous decisions.

All autonomous actions are expressed as DecisionRequests that flow
through the Control Plane governance pipeline.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DecisionDomain(Enum):
    """Domain of the decision request."""
    RESEARCH = "research"
    ALPHA = "alpha"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    EXECUTION = "execution"
    SYSTEM = "system"


class DecisionAction(Enum):
    """Type of action being requested."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PROMOTE = "promote"
    DEMOTE = "demote"
    EXECUTE = "execute"
    ALLOCATE = "allocate"
    DEALLOCATE = "deallocate"
    ROLLBACK = "rollback"
    QUARANTINE = "quarantine"


@dataclass
class DecisionRequest:
    """
    Standardized autonomous decision request.

    Every autonomous action — from "run a backtest" to "execute a live
    order" — is wrapped as a DecisionRequest and passed through the
    Control Plane for governance evaluation.
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # Entity
    domain: DecisionDomain = DecisionDomain.SYSTEM
    action_type: DecisionAction = DecisionAction.CREATE
    entity_id: str = ""
    entity_type: str = ""

    # Context
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    research_id: Optional[str] = None
    alpha_id: Optional[str] = None

    # Risk
    risk_context: Optional[dict] = field(default_factory=dict)
    market_context: Optional[dict] = field(default_factory=dict)

    # Governance
    policy_context: Optional[dict] = field(default_factory=dict)
    autonomy_level: int = 0
    requested_scope: str = "default"

    # Parameters
    params: dict = field(default_factory=dict)
    requested_capital: float = 0.0
    requested_duration_days: int = 0

    # Lineage
    parent_decision_id: Optional[str] = None

    def to_context_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "trace_id": self.trace_id,
            "domain": self.domain.value,
            "action_type": self.action_type.value,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "research_id": self.research_id,
            "alpha_id": self.alpha_id,
            "risk_context": self.risk_context,
            "market_context": self.market_context,
            "policy_context": self.policy_context,
            "autonomy_level": self.autonomy_level,
            "requested_scope": self.requested_scope,
            "params": self.params,
            "requested_capital": self.requested_capital,
            "requested_duration_days": self.requested_duration_days,
            "parent_decision_id": self.parent_decision_id,
        }
