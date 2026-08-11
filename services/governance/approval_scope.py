"""
Approval Scope — defines what scope an approval covers and enforces binding.

An approval for Strategy A cannot be used for Strategy B.
An approval for Portfolio A cannot be used for Portfolio B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ApprovalScopeLevel(Enum):
    """Scope granularity for approvals."""
    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    PORTFOLIO = "PORTFOLIO"
    STRATEGY = "STRATEGY"
    ASSET = "ASSET"
    ORDER = "ORDER"
    CAPITAL = "CAPITAL"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    POSITION = "POSITION"


@dataclass
class ApprovalScope:
    """
    Defines the scope within which an approval is valid.

    Rules:
      - scope_id binds to a specific entity (e.g., "PORTFOLIO_A")
      - allowed_actions restrict what the approval can be used for
      - excludes explicitly denies certain sub-scopes
    """

    level: ApprovalScopeLevel = ApprovalScopeLevel.GLOBAL
    scope_id: str = ""  # Entity identifier (e.g., "PORTFOLIO_A")
    description: str = ""

    # What actions are approved within this scope
    allowed_actions: List[str] = field(default_factory=list)

    # Explicit exclusions within broader scope
    excludes: List[str] = field(default_factory=list)

    # Patterns (regex) for matching
    pattern: str = ""

    def applies_to(self, target_level: ApprovalScopeLevel, target_id: str = "",
                   action: str = "") -> bool:
        """Check if this scope covers a target."""
        # Level check: GLOBAL covers everything
        if self.level == ApprovalScopeLevel.GLOBAL:
            level_ok = True
        else:
            level_ok = (self.level == target_level)

        if not level_ok:
            return False

        # ID check
        if self.scope_id and target_id and self.scope_id != target_id:
            return False

        # Exclusion check
        if target_id and target_id in self.excludes:
            return False

        # Action check
        if action and self.allowed_actions:
            if action not in self.allowed_actions:
                return False

        return True

    def matches_action(self, action: str) -> bool:
        """Check if this scope permits a specific action."""
        if not self.allowed_actions:
            return True
        return action in self.allowed_actions

    @classmethod
    def global_scope(cls) -> "ApprovalScope":
        return cls(level=ApprovalScopeLevel.GLOBAL, description="Global scope")

    @classmethod
    def portfolio_scope(cls, portfolio_id: str) -> "ApprovalScope":
        return cls(
            level=ApprovalScopeLevel.PORTFOLIO,
            scope_id=portfolio_id,
            description=f"Portfolio: {portfolio_id}",
        )

    @classmethod
    def strategy_scope(cls, strategy_id: str) -> "ApprovalScope":
        return cls(
            level=ApprovalScopeLevel.STRATEGY,
            scope_id=strategy_id,
            description=f"Strategy: {strategy_id}",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "scope_id": self.scope_id,
            "description": self.description,
            "allowed_actions": self.allowed_actions,
            "excludes": self.excludes,
        }
