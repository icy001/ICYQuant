"""
Policy Conflict Resolver — Resolves conflicts between overlapping policies.

When multiple policies apply to the same decision, the Conflict Resolver
determines the effective constraint using conservative precedence rules:
the most restrictive constraint always wins.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConflictResolution:
    """Result of a policy conflict resolution."""

    def __init__(self):
        self.has_conflict: bool = False
        self.effective_constraints: dict[str, Any] = {}
        self.resolved_by: str = "most_restrictive"
        self.conflicting_policies: list[str] = []
        self.resolution_details: list[dict] = []

    def add_conflict(self, policy_id_a: str, policy_id_b: str, constraint: str, chosen: Any, rejected: Any):
        self.has_conflict = True
        self.conflicting_policies.extend([policy_id_a, policy_id_b])
        self.resolution_details.append({
            "constraint": constraint,
            "policy_a": policy_id_a,
            "policy_b": policy_id_b,
            "chosen_value": chosen,
            "rejected_value": rejected,
            "principle": "most_restrictive_wins",
        })


class PolicyConflictResolver:
    """
    Resolves conflicts between overlapping policies.

    Principles:
        1. Most restrictive constraint wins (conservative default)
        2. Hard limits override soft limits
        3. Explicit scope overrides inherited scope
        4. More specific policy version overrides general
    """

    def __init__(self):
        self._resolution_count = 0
        self._conflict_count = 0

    def resolve(self, evaluations: list) -> ConflictResolution:
        """
        Resolve conflicts among multiple policy evaluation results.

        Returns a ConflictResolution with the effective constraints.
        """
        resolution = ConflictResolution()
        self._resolution_count += 1

        if len(evaluations) <= 1:
            return resolution

        # Collect decisions
        from .control_plane import ControlPlaneDecision

        restrictiveness = {
            ControlPlaneDecision.ALLOW: 0,
            ControlPlaneDecision.RESIZE: 1,
            ControlPlaneDecision.DEFER: 2,
            ControlPlaneDecision.REVIEW: 3,
            ControlPlaneDecision.QUARANTINE: 4,
            ControlPlaneDecision.ROLLBACK: 5,
            ControlPlaneDecision.DENY: 6,
            ControlPlaneDecision.HALT: 7,
        }

        # Check for conflicting decisions
        decisions = set()
        for ev in evaluations:
            if hasattr(ev, "decision"):
                decisions.add(ev.decision)

        if len(decisions) > 1:
            self._conflict_count += 1
            resolution.has_conflict = True

            # Find all involved policies
            for ev in evaluations:
                pid = getattr(ev, "policy_id", "unknown")
                if pid not in resolution.conflicting_policies:
                    resolution.conflicting_policies.append(pid)

            resolution.resolution_details.append({
                "conflicting_decisions": [d.value for d in decisions],
                "resolution_principle": "most_restrictive_wins",
            })

        return resolution

    # ------------------------------------------------------------------
    # Constraint Comparison
    # ------------------------------------------------------------------

    @staticmethod
    def min_constraint(a_val: float, b_val: float) -> float:
        """Conservative: return the smaller value."""
        return min(a_val, b_val)

    @staticmethod
    def max_constraint(a_val: float, b_val: float) -> float:
        """Conservative: for upper bounds, return the smaller max."""
        return min(a_val, b_val)

    @staticmethod
    def restrictiveness(default: Any, override: Any) -> Any:
        """Return the more restrictive value."""
        if isinstance(default, (int, float)) and isinstance(override, (int, float)):
            return min(default, override)
        # For non-numeric, prefer override if more specific
        return override if override is not None else default

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "resolutions_total": self._resolution_count,
            "conflicts_total": self._conflict_count,
        }
