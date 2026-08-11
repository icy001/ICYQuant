"""
Approval Threshold — tiered approval levels based on decision amounts.

Defines the mapping: decision amount → required approval authority level.
These thresholds are used by the Approval Engine to determine if a decision
needs approval and at what level (AUTONOMOUS, RISK_MANAGER, etc.).

Key principle:
    Threshold determines WHAT LEVEL of authority is needed,
    NOT the trading direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ApprovalThreshold:
    """
    A complete threshold table for a decision type.

    Example:
        CAPITAL_ALLOCATION:

        0 - 5M      → AUTONOMOUS
        5M - 20M    → RISK_MANAGER
        20M - 50M   → RISK_MANAGER + PORTFOLIO_MANAGER
        > 50M       → INVESTMENT_COMMITTEE
    """

    threshold_id: str
    name: str
    decision_type: str

    # Ordered tiers (must be sorted by max_amount ascending)
    tiers: List[ThresholdTier] = field(default_factory=list)

    # Fallback when no tier matches
    default_authority_level: str = "AUTONOMOUS"

    # Whether to require ALL authorities or ANY when multiple are listed
    require_all: bool = True

    def resolve(self, amount: float) -> ThresholdResult:
        """Resolve the required authority level(s) for a given amount."""
        sorted_tiers = sorted(self.tiers, key=lambda t: t.max_amount)
        for tier in sorted_tiers:
            if amount <= tier.max_amount:
                return ThresholdResult(
                    threshold_id=self.threshold_id,
                    decision_type=self.decision_type,
                    amount=amount,
                    matched_tier=tier.name,
                    authority_levels=list(tier.authority_levels),
                    require_all=self.require_all,
                    approval_required=len(tier.authority_levels) > 0,
                )
        # Fallback
        fallback_levels = [self.default_authority_level] if self.default_authority_level != "AUTONOMOUS" else []
        return ThresholdResult(
            threshold_id=self.threshold_id,
            decision_type=self.decision_type,
            amount=amount,
            matched_tier="DEFAULT",
            authority_levels=fallback_levels,
            require_all=self.require_all,
            approval_required=len(fallback_levels) > 0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "name": self.name,
            "decision_type": self.decision_type,
            "tiers": [t.to_dict() for t in self.tiers],
            "default_authority_level": self.default_authority_level,
            "require_all": self.require_all,
        }


@dataclass
class ThresholdTier:
    """A single tier: amount threshold → authority level(s)."""

    name: str
    max_amount: float
    authority_levels: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "max_amount": self.max_amount,
            "authority_levels": self.authority_levels,
            "description": self.description,
        }


@dataclass
class ThresholdResult:
    """Resolved authority requirements for a given amount."""

    threshold_id: str
    decision_type: str
    amount: float
    matched_tier: str
    authority_levels: List[str]
    require_all: bool = True
    approval_required: bool = False

    def has_level(self, level: str) -> bool:
        """Check if a specific authority level is required."""
        return level in self.authority_levels

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "decision_type": self.decision_type,
            "amount": self.amount,
            "matched_tier": self.matched_tier,
            "authority_levels": self.authority_levels,
            "require_all": self.require_all,
            "approval_required": self.approval_required,
        }
