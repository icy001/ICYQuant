"""
Authority Limit — defines the quantitative boundaries of an authority grant.

Every authority has explicit limits on:
  - Maximum amount they can approve
  - Maximum risk they can approve
  - Maximum leverage they can approve
  - Allowed actions (specific decision types)

These limits are enforced at runtime by the AuthorityEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AuthorityLimit:
    """
    Quantitative boundaries for an authority grant.

    Example:
        Risk Manager:
            max_amount = 20_000_000  (20M)
            max_risk = 2_000_000     (2M)
            allowed_actions = [APPROVE_ALLOCATION, APPROVE_RISK_REDUCTION]
    """

    limit_id: str

    # Quantitative limits
    max_amount: float = float("inf")
    max_risk: float = float("inf")
    max_leverage: float = float("inf")

    # Action limits
    allowed_actions: List[str] = field(default_factory=list)

    # Duration
    valid_from: float = 0.0
    valid_to: float = float("inf")

    def allows_amount(self, amount: float) -> bool:
        """Check if the given amount is within the limit."""
        return amount <= self.max_amount

    def allows_risk(self, risk: float) -> bool:
        """Check if the given risk is within the limit."""
        return risk <= self.max_risk

    def allows_action(self, action: str) -> bool:
        """Check if the given action is allowed."""
        if not self.allowed_actions:
            return True  # No restriction on actions
        return action in self.allowed_actions

    def is_active(self, current_time: float) -> bool:
        """Check if the limit is currently active."""
        return self.valid_from <= current_time <= self.valid_to

    def exceeded(self, amount: float = 0.0, risk: float = 0.0, action: str = "") -> Dict[str, Any]:
        """
        Check which limits would be exceeded.

        Returns a dict with the exceeded fields and their limits.
        """
        violations: Dict[str, Any] = {}
        if amount > self.max_amount:
            violations["amount"] = {"requested": amount, "max": self.max_amount}
        if risk > self.max_risk:
            violations["risk"] = {"requested": risk, "max": self.max_risk}
        if action and not self.allows_action(action):
            violations["action"] = f"'{action}' is not in allowed actions"
        return violations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "limit_id": self.limit_id,
            "max_amount": self.max_amount,
            "max_risk": self.max_risk,
            "max_leverage": self.max_leverage,
            "allowed_actions": self.allowed_actions,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
        }
