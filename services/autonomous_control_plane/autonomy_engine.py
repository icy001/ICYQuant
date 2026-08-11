"""
Autonomy Engine — Level-based autonomy control.

Controls what the autonomous system can do based on its current
autonomy level, ensuring progressive trust and safety.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AutonomyLevel(IntEnum):
    """Autonomy levels for the ICYQuant autonomous system."""
    L0_OBSERVE = 0       # Read-only observation
    L1_RESEARCH = 1      # Autonomous research allowed
    L2_RECOMMEND = 2     # Strategy/alpha recommendation
    L3_SIMULATE = 3      # Paper trading / simulation
    L4_PAPER_TRADE = 4   # Paper trade execution
    L5_RISK_GOVERNED = 5 # Risk-governed live execution
    L6_PRODUCTION = 6    # Full production autonomy

    @classmethod
    def from_int(cls, level: int) -> "AutonomyLevel":
        try:
            return cls(level)
        except ValueError:
            return cls.L0_OBSERVE


# Permission matrix: what each level can do
AUTONOMY_PERMISSIONS = {
    AutonomyLevel.L0_OBSERVE: {
        "research": False,
        "generate_alpha": False,
        "generate_strategy": False,
        "paper_trade": False,
        "risk_optimization": False,
        "live_order_proposal": False,
        "autonomous_execution": False,
        "full_production": False,
    },
    AutonomyLevel.L1_RESEARCH: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": False,
        "paper_trade": False,
        "risk_optimization": False,
        "live_order_proposal": False,
        "autonomous_execution": False,
        "full_production": False,
    },
    AutonomyLevel.L2_RECOMMEND: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": True,
        "paper_trade": False,
        "risk_optimization": False,
        "live_order_proposal": False,
        "autonomous_execution": False,
        "full_production": False,
    },
    AutonomyLevel.L3_SIMULATE: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": True,
        "paper_trade": True,
        "risk_optimization": True,
        "live_order_proposal": False,
        "autonomous_execution": False,
        "full_production": False,
    },
    AutonomyLevel.L4_PAPER_TRADE: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": True,
        "paper_trade": True,
        "risk_optimization": True,
        "live_order_proposal": True,
        "autonomous_execution": False,
        "full_production": False,
    },
    AutonomyLevel.L5_RISK_GOVERNED: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": True,
        "paper_trade": True,
        "risk_optimization": True,
        "live_order_proposal": True,
        "autonomous_execution": True,
        "full_production": False,
    },
    AutonomyLevel.L6_PRODUCTION: {
        "research": True,
        "generate_alpha": True,
        "generate_strategy": True,
        "paper_trade": True,
        "risk_optimization": True,
        "live_order_proposal": True,
        "autonomous_execution": True,
        "full_production": True,
    },
}


@dataclass
class AutonomyDecision:
    """Result of an autonomy engine evaluation."""
    allowed: bool
    decision: Any  # ControlPlaneDecision
    level: int = 0
    reason: str = ""
    missing_permissions: list[str] = None

    def __post_init__(self):
        if self.missing_permissions is None:
            self.missing_permissions = []


class AutonomyEngine:
    """
    Evaluates whether the current autonomy level permits a requested action.

    Every autonomous decision passes through the Autonomy Engine to verify
    that the action is within the system's granted autonomy level.
    """

    def __init__(self, current_level: int = 2):
        self._current_level = current_level
        self._evaluation_count = 0
        self._denial_count = 0
        self._transition_history: list[dict] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        logger.info("AutonomyEngine started at L%d", self._current_level)

    # ------------------------------------------------------------------
    # Level Management
    # ------------------------------------------------------------------

    async def current_level(self) -> int:
        return self._current_level

    def set_level(self, level: int, reason: str = "", operator: str = "") -> bool:
        """Set the autonomy level."""
        if level < 0 or level > 6:
            return False
        old = self._current_level
        self._current_level = level
        self._transition_history.append({
            "from": old, "to": level, "reason": reason,
            "operator": operator, "timestamp": __import__("time").time(),
        })
        logger.warning("Autonomy level changed: L%d → L%d (%s)", old, level, reason)
        return True

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, context) -> AutonomyDecision:
        """Evaluate if the requested action is within autonomy limits."""
        from .control_plane import ControlPlaneDecision

        self._evaluation_count += 1
        level = AutonomyLevel.from_int(self._current_level)
        permissions = AUTONOMY_PERMISSIONS.get(level, AUTONOMY_PERMISSIONS[AutonomyLevel.L0_OBSERVE])

        requested = getattr(context, "requested_scope", "unknown")
        action = getattr(context, "action", "evaluate")

        # Map requested scope to permission key
        permission_key = self._map_to_permission(requested, action)

        if permission_key in permissions and permissions[permission_key]:
            return AutonomyDecision(
                allowed=True,
                decision=ControlPlaneDecision.ALLOW,
                level=self._current_level,
            )

        self._denial_count += 1
        return AutonomyDecision(
            allowed=False,
            decision=ControlPlaneDecision.DENY,
            level=self._current_level,
            reason=f"Action '{action}' requires higher autonomy than L{self._current_level}",
            missing_permissions=[permission_key],
        )

    def _map_to_permission(self, scope: str, action: str) -> str:
        """Map a scope/action to a permission key."""
        if scope == "research" or action == "run_research":
            return "research"
        if scope == "alpha" or action == "generate_alpha":
            return "generate_alpha"
        if scope == "strategy" or action == "generate_strategy":
            return "generate_strategy"
        if scope == "paper_trade":
            return "paper_trade"
        if scope == "risk" or action == "risk_optimize":
            return "risk_optimization"
        if scope == "execution" or action == "propose_order":
            return "live_order_proposal"
        if scope == "autonomous_execution" or action == "execute_autonomously":
            return "autonomous_execution"
        if scope == "production" or action == "full_autonomy":
            return "full_production"
        return scope

    # ------------------------------------------------------------------
    # Transition Validation
    # ------------------------------------------------------------------

    def can_transition_to(self, target_level: int) -> tuple[bool, str]:
        """Check if a level transition is valid."""
        if target_level < 0 or target_level > 6:
            return False, "Invalid level"
        if target_level == self._current_level:
            return True, "Same level"
        if target_level > self._current_level + 1:
            return False, "Must increase one level at a time"
        return True, ""

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "current_level": self._current_level,
            "evaluations_total": self._evaluation_count,
            "denials_total": self._denial_count,
            "transitions_total": len(self._transition_history),
            "permissions": AUTONOMY_PERMISSIONS.get(
                AutonomyLevel.from_int(self._current_level),
                {},
            ),
        }
