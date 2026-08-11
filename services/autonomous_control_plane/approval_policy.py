"""
Approval Policy — Rules governing when approval is required.

Defines thresholds and conditions that trigger mandatory human approval.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ApprovalPolicy:
    """
    Defines when human approval is required for autonomous actions.

    Thresholds can be configured per domain and action type.
    """

    def __init__(self):
        # Capital threshold requiring approval
        self.capital_approval_threshold: float = 100_000.0

        # Autonomy levels requiring approval for specific actions
        self.approval_levels: dict[str, int] = {
            "autonomous_execution": 5,
            "full_production": 6,
            "large_capital": 5,
        }

        # Domains requiring approval
        self.approval_domains = {
            "production": True,
            "capital": True,
        }

    def requires_approval(self, scope: str, action: str, capital: float = 0.0, autonomy_level: int = 0) -> tuple[bool, str]:
        """Determine if a decision requires human approval."""
        reasons = []

        if scope in self.approval_domains and self.approval_domains[scope]:
            reasons.append(f"Scope '{scope}' requires approval")

        if capital > self.capital_approval_threshold:
            reasons.append(f"Capital {capital} exceeds threshold {self.capital_approval_threshold}")

        required_level = self.approval_levels.get(action, 6)
        if autonomy_level < required_level:
            reasons.append(f"Action '{action}' requires L{required_level}+ with approval")

        return len(reasons) > 0, "; ".join(reasons) if reasons else ""

    def stats(self) -> dict:
        return {
            "capital_threshold": self.capital_approval_threshold,
            "approval_levels": self.approval_levels,
            "approval_domains": list(self.approval_domains.keys()),
        }
