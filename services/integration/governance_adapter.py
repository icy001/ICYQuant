"""
Governance Adapter — bridges Governance Engine into the integration control flow.

Commit 21 Part 1.1: translates governance state, policy results, and
control decisions into a normalized governance_context consumed by GovernanceGate.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class GovernanceAdapter:
    """Bridges Governance Engine to integration layer.

    Domain (Governance) → Adapter → Integration Layer (GovernanceGate)
    """

    @staticmethod
    def build_governance_context(
        governance_state: str = "NORMAL",
        emergency_mode: bool = False,
        frozen: bool = False,
        policy_violations: Optional[list] = None,
        blocked_strategies: Optional[list] = None,
        trading_halted: bool = False,
        active_policy_count: int = 0,
        policy_conflicts: int = 0,
        governance_version: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """Build a governance context dict for integration gates."""
        return {
            "governance_state": governance_state,
            "state": governance_state,
            "emergency_mode": emergency_mode,
            "frozen": frozen,
            "policy_violations": policy_violations or [],
            "blocked_strategies": blocked_strategies or [],
            "trading_halted": trading_halted,
            "active_policy_count": active_policy_count,
            "policy_conflicts": policy_conflicts,
            "governance_version": governance_version,
            **kwargs,
        }

    @staticmethod
    def from_governance_policy_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert governance policy evaluation result to integration context."""
        return {
            "governance_state": result.get("governance_state", "NORMAL"),
            "state": result.get("governance_state", "NORMAL"),
            "emergency_mode": result.get("emergency_mode", False),
            "frozen": result.get("frozen",
                                  result.get("governance_state") == "FROZEN"),
            "policy_violations": result.get("violations",
                                            result.get("policy_violations", [])),
            "active_policy_count": result.get("active_policy_count", 0),
            "policy_conflicts": result.get("policy_conflicts", 0),
            "governance_version": result.get("governance_version", ""),
            "passed": result.get("passed", result.get("allowed", True)),
            "reason": result.get("reason", ""),
        }

    @staticmethod
    def from_governance_state(state_obj: Any) -> Dict[str, Any]:
        """Extract governance state from state object."""
        return {
            "governance_state": getattr(state_obj, "name", str(state_obj)),
            "state": getattr(state_obj, "name", str(state_obj)),
            "emergency_mode": getattr(state_obj, "emergency_mode", False),
            "frozen": getattr(state_obj, "frozen", False),
            "trading_halted": getattr(state_obj, "trading_halted", False),
            "allows_new_risk": getattr(state_obj, "allows_new_risk", True),
            "allows_new_orders": getattr(state_obj, "allows_new_orders", True),
        }
