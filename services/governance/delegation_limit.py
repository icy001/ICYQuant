"""
Delegation Limit — quantitative bounds on a delegated authority.

Must satisfy: delegation limit <= original authority limit.
Cannot expand the delegator's own limits through delegation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .authority_limit import AuthorityLimit


@dataclass
class DelegationLimit:
    """
    Quantitative boundaries for a delegated authority.

    Every dimension must be <= the original authority's limit:
      - Amount
      - Risk
      - Leverage
      - Actions
      - Duration
    """
    limit_id: str

    # Quantitative limits (all must be <= parent)
    max_amount: float = float("inf")
    max_risk: float = float("inf")
    max_leverage: float = float("inf")

    # Action limits (subset of parent allowed actions)
    allowed_actions: List[str] = field(default_factory=list)

    # Duration (must be within parent's valid window)
    valid_from: float = 0.0
    valid_to: float = float("inf")

    def is_subset_of(self, parent: AuthorityLimit) -> bool:
        """Check that this delegation limit is a subset of the parent limit."""
        violations: List[str] = []

        if self.max_amount > parent.max_amount:
            violations.append(
                f"amount {self.max_amount} exceeds parent limit {parent.max_amount}"
            )
        if self.max_risk > parent.max_risk:
            violations.append(
                f"risk {self.max_risk} exceeds parent limit {parent.max_risk}"
            )
        if self.max_leverage > parent.max_leverage:
            violations.append(
                f"leverage {self.max_leverage} exceeds parent limit {parent.max_leverage}"
            )
        if self.valid_to > parent.valid_to:
            violations.append(
                f"valid_to {self.valid_to} exceeds parent valid_to {parent.valid_to}"
            )

        # Check actions are subset
        if parent.allowed_actions:
            for action in self.allowed_actions:
                if action not in parent.allowed_actions:
                    violations.append(
                        f"action '{action}' is not in parent allowed actions"
                    )

        return len(violations) == 0

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
