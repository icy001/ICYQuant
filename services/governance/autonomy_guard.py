"""
Autonomy Guard — ensures autonomy level is respected.

Links governance to Commit 19's autonomy level system, preventing
lower-autonomy actors from exceeding their permitted decision scope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .authority_policy import AuthorityLevel
from .autonomy_constraint import AutonomyConstraint
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class AutonomyGuard:
    """
    Ensures actors operate within their autonomy level boundaries.
    """

    def __init__(self, constraint: Optional[AutonomyConstraint] = None):
        self._constraint = constraint or AutonomyConstraint()
        self._blocks: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, request: DecisionRequest, context: DecisionContext) -> Dict[str, Any]:
        """Check if decision is within autonomy boundaries."""
        result = self._constraint.evaluate(request, context)

        if not result.passed:
            self._blocks.append({
                "request_id": request.request_id,
                "actor": request.actor,
                "autonomy_level": context.actor_autonomy_level,
                "decision_type": request.decision_type.name,
                "reason": result.reason,
                "timestamp": request.timestamp,
            })
            return {"pass": False, "reason": result.reason}

        return {"pass": True, "reason": "Within autonomy boundary"}

    def is_allowed(self, request: DecisionRequest, context: DecisionContext) -> bool:
        return self.check(request, context)["pass"]

    # ------------------------------------------------------------------
    # Autonomy level queries
    # ------------------------------------------------------------------

    def get_allowed_decisions(self, level: int) -> List[str]:
        """List all decision types allowed at a given autonomy level."""
        perms = self._constraint.permissions.get(level, {})
        return [dt for dt, allowed in perms.items() if allowed]

    def get_required_level(self, decision_type: str) -> Optional[int]:
        """Get the minimum autonomy level required for a decision type."""
        for level in sorted(self._constraint.permissions.keys()):
            if self._constraint.permissions[level].get(decision_type, False):
                return level
        return None

    # ------------------------------------------------------------------
    # Boundary enforcement
    # ------------------------------------------------------------------

    def enforce_boundary(
        self, request: DecisionRequest, context: DecisionContext
    ) -> Dict[str, Any]:
        """
        Enforce autonomy boundaries with specific rules:
        - Risk-increasing decisions require AUTONOMOUS_ALLOCATION or higher
        - Capital allocation requires AUTONOMOUS_ALLOCATION
        - Emergency actions require EMERGENCY_RISK_CONTROL
        """
        level = context.actor_autonomy_level

        # Specific boundary rules
        if request.is_risk_increasing:
            if level < AuthorityLevel.AUTONOMOUS_ALLOCATION:
                return {
                    "pass": False,
                    "reason": f"Risk-increasing decisions require AUTONOMOUS_ALLOCATION (level 3), "
                             f"current level: {level}",
                }

        if request.emergency and level < AuthorityLevel.EMERGENCY_RISK_CONTROL:
            return {
                "pass": False,
                "reason": f"Emergency decisions require EMERGENCY_RISK_CONTROL (level 4), "
                         f"current level: {level}",
            }

        return self.check(request, context)

    # ------------------------------------------------------------------
    # Blocks log
    # ------------------------------------------------------------------

    def get_blocks(self) -> List[Dict[str, Any]]:
        return list(self._blocks)

    def clear_blocks(self) -> None:
        self._blocks.clear()
