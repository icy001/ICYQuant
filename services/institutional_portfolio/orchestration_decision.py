"""
Orchestration Decision — Unified Portfolio Decision Output

All portfolio orchestration actions produce a unified decision:
    NET, ALLOCATE, REDUCE, REBALANCE, RESERVE, FREEZE, REPLACE, QUARANTINE, HOLD
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    NET = "NET"
    ALLOCATE = "ALLOCATE"
    REDUCE = "REDUCE"
    REBALANCE = "REBALANCE"
    RESERVE = "RESERVE"
    FREEZE = "FREEZE"
    REPLACE = "REPLACE"
    QUARANTINE = "QUARANTINE"
    HOLD = "HOLD"


@dataclass
class OrchestrationDecision:
    decision_id: str
    decision_type: DecisionType
    strategy_id: Optional[str] = None
    asset: Optional[str] = None
    amount: float = 0.0
    reason: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.utcnow)
    upstream_decisions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrchestrationDecisionMaker:
    """
    Produces unified orchestration decisions for all portfolio actions.

    Every portfolio action produces an OrchestrationDecision with:
    - Decision type (NET, ALLOCATE, REBALANCE, etc.)
    - Associated strategy/asset
    - Amount, reason, confidence
    - Upstream decision trace for lineage
    """

    def __init__(
        self,
        maker_id: Optional[str] = None,
    ):
        self.maker_id = maker_id or f"odm-{uuid.uuid4().hex[:12]}"
        self._decisions: List[OrchestrationDecision] = []

    def decide(
        self,
        decision_type: DecisionType,
        strategy_id: Optional[str] = None,
        asset: Optional[str] = None,
        amount: float = 0.0,
        reason: str = "",
        confidence: float = 0.5,
    ) -> OrchestrationDecision:
        decision = OrchestrationDecision(
            decision_id=f"dec-{uuid.uuid4().hex[:8]}",
            decision_type=decision_type,
            strategy_id=strategy_id,
            asset=asset,
            amount=amount,
            reason=reason,
            confidence=confidence,
        )
        self._decisions.append(decision)
        return decision

    def get_decisions(self) -> List[OrchestrationDecision]:
        return list(self._decisions)

    def get_decisions_by_type(self, decision_type: DecisionType) -> List[OrchestrationDecision]:
        return [d for d in self._decisions if d.decision_type == decision_type]
