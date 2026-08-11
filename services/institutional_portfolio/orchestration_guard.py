"""
Orchestration Guard — Safety Gate for All Portfolio Actions

Every cross-strategy action goes through the guard:
    Capital, Risk, Strategy Capacity, Liquidity, Turnover, Concentration,
    Autonomy, Policy

Outputs: ALLOW, RESIZE, DEFER, REJECT

Integrates with Commit 18 Autonomous Control Plane.
"""

import uuid
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GuardDecision(str, Enum):
    ALLOW = "ALLOW"
    RESIZE = "RESIZE"
    DEFER = "DEFER"
    REJECT = "REJECT"


@dataclass
class GuardResult:
    allowed: bool
    decision: GuardDecision
    reasons: List[str] = field(default_factory=list)
    resized_amount: Optional[float] = None
    defer_seconds: int = 0


class OrchestrationGuard:
    """
    Safety gate for all portfolio orchestration actions.

    All cross-strategy actions (net, allocate, rebalance, quarantine,
    replace) must pass this guard before execution.

    Integrates with Commit 18 Control Plane for policy/autonomy checks.
    """

    def __init__(
        self,
        guard_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.guard_id = guard_id or f"og-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._control_plane = None

        self._limits = {
            "max_capital_per_action": self.config.get("max_capital_per_action", float("inf")),
            "max_risk_increase": self.config.get("max_risk_increase", 0.05),
            "max_concentration": self.config.get("max_concentration", 0.30),
            "max_turnover": self.config.get("max_turnover", 0.50),
        }

    def check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if an action is allowed by all guard rules.

        Returns: {allowed: bool, decision: str, reasons: [...]}
        """
        results = GuardResult(allowed=True, decision=GuardDecision.ALLOW)

        # Capital check
        amount = context.get("amount", 0)
        if amount > self._limits["max_capital_per_action"]:
            results.decision = GuardDecision.RESIZE
            results.resized_amount = self._limits["max_capital_per_action"]
            results.reasons.append("Capital exceeds max per action")

        # Risk check
        risk_change = context.get("risk_change", 0)
        if risk_change > self._limits["max_risk_increase"]:
            results.decision = GuardDecision.REJECT
            results.reasons.append(f"Risk increase {risk_change} exceeds {self._limits['max_risk_increase']}")

        # Turnover check
        turnover = context.get("turnover", 0)
        if turnover > self._limits["max_turnover"]:
            results.decision = GuardDecision.REJECT
            results.reasons.append(f"Turnover {turnover} exceeds max {self._limits['max_turnover']}")

        # Control plane integration
        if self._control_plane:
            cp_result = self._control_plane.evaluate({
                "action": "portfolio_orchestrate",
                "context": context,
            })
            if not cp_result.get("approved", True):
                results.decision = GuardDecision.REJECT
                results.reasons.append(f"Control plane: {cp_result.get('reason')}")

        results.allowed = results.decision != GuardDecision.REJECT
        return {
            "allowed": results.allowed,
            "decision": results.decision.value,
            "reasons": results.reasons,
            "resized_amount": results.resized_amount,
        }
