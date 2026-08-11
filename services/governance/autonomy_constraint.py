"""
Autonomy Constraint — enforces autonomy level boundaries.

Prevents lower-autonomy actors from making decisions beyond their permitted level.
Links directly to Commit 19's Autonomy Level system.
"""

from __future__ import annotations

from typing import Dict, Optional

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class AutonomyConstraint(GovernanceConstraint):
    """
    Enforces that decisions are within the actor's autonomy level.
    """

    # What each autonomy level can do
    DEFAULT_PERMISSIONS: Dict[int, Dict[str, bool]] = {
        0: {  # MANUAL
            "CAPITAL_ALLOCATION": False,
            "CAPITAL_REBALANCE": False,
            "RISK_BUDGET_CHANGE": False,
            "LEVERAGE_CHANGE": False,
            "ORDER_SUBMIT": False,
            "EMERGENCY_ACTION": False,
        },
        1: {  # RECOMMENDATION
            "CAPITAL_ALLOCATION": False,
            "CAPITAL_REBALANCE": False,
            "RISK_BUDGET_CHANGE": False,
            "LEVERAGE_CHANGE": False,
            "ORDER_SUBMIT": True,
            "EMERGENCY_ACTION": False,
        },
        2: {  # AUTO_REBALANCE
            "CAPITAL_ALLOCATION": False,
            "CAPITAL_REBALANCE": True,
            "RISK_BUDGET_CHANGE": False,
            "LEVERAGE_CHANGE": False,
            "ORDER_SUBMIT": True,
            "EMERGENCY_ACTION": False,
        },
        3: {  # AUTONOMOUS_ALLOCATION
            "CAPITAL_ALLOCATION": True,
            "CAPITAL_REBALANCE": True,
            "RISK_BUDGET_CHANGE": True,
            "LEVERAGE_CHANGE": False,
            "ORDER_SUBMIT": True,
            "EMERGENCY_ACTION": False,
        },
        4: {  # EMERGENCY_RISK_CONTROL
            "CAPITAL_ALLOCATION": False,   # Don't increase risk
            "CAPITAL_REBALANCE": False,
            "RISK_BUDGET_CHANGE": True,
            "LEVERAGE_CHANGE": True,
            "ORDER_SUBMIT": True,
            "EMERGENCY_ACTION": True,
        },
    }

    def __init__(
        self,
        permissions: Optional[Dict[int, Dict[str, bool]]] = None,
        blocking: bool = True,
    ):
        super().__init__(name="autonomy", blocking=blocking)
        self.permissions = permissions or self.DEFAULT_PERMISSIONS

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        level = context.actor_autonomy_level
        decision_type = request.decision_type.name

        level_perms = self.permissions.get(level, {})

        if not level_perms.get(decision_type, False):
            return ConstraintResult.fail(
                self.name,
                reason=(f"Autonomy level {level} does not permit '{decision_type}'. "
                        f"Minimum level required: {self._min_level_for(decision_type)}"),
                blocking=self.blocking,
                actual=level,
                limit=self._min_level_for(decision_type),
            )

        # Emergency decisions require emergency mode
        if decision_type == "EMERGENCY_ACTION" and not context.emergency_mode:
            return ConstraintResult.fail(
                self.name,
                reason="EMERGENCY_ACTION requires emergency mode to be active",
                blocking=self.blocking,
            )

        return ConstraintResult.pass_(self.name)

    def _min_level_for(self, decision_type: str) -> int:
        for level in sorted(self.permissions.keys()):
            if self.permissions[level].get(decision_type, False):
                return level
        return 99  # Not permitted at any level
