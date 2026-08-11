"""
Authority Scope — defines the domain boundaries of an authority grant.

Each authority operates within a scope that limits what they can approve.
Scopes nest hierarchically: GLOBAL > ACCOUNT > PORTFOLIO > STRATEGY > ORDER.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Authority scope levels
# ---------------------------------------------------------------------------

class AuthorityScopeLevel(Enum):
    """Hierarchical authority scope levels."""
    GLOBAL = auto()        # System-wide authority
    ACCOUNT = auto()       # Account-level
    PORTFOLIO = auto()     # Portfolio-level
    STRATEGY = auto()      # Strategy-level
    ASSET = auto()         # Asset-level
    FACTOR = auto()        # Factor-level
    ORDER = auto()         # Order-level
    EXECUTION = auto()     # Execution-level
    CAPITAL = auto()       # Capital-specific
    MARKET = auto()        # Market-specific
    RISK = auto()          # Risk-specific


# Scope hierarchy: parent → children
_SCOPE_HIERARCHY: Dict[AuthorityScopeLevel, FrozenSet[AuthorityScopeLevel]] = {
    AuthorityScopeLevel.GLOBAL: frozenset({
        AuthorityScopeLevel.ACCOUNT,
        AuthorityScopeLevel.CAPITAL,
        AuthorityScopeLevel.MARKET,
        AuthorityScopeLevel.RISK,
    }),
    AuthorityScopeLevel.ACCOUNT: frozenset({
        AuthorityScopeLevel.PORTFOLIO,
    }),
    AuthorityScopeLevel.PORTFOLIO: frozenset({
        AuthorityScopeLevel.STRATEGY,
        AuthorityScopeLevel.ASSET,
        AuthorityScopeLevel.FACTOR,
    }),
    AuthorityScopeLevel.STRATEGY: frozenset({
        AuthorityScopeLevel.ORDER,
        AuthorityScopeLevel.EXECUTION,
    }),
    AuthorityScopeLevel.ASSET: frozenset(),
    AuthorityScopeLevel.FACTOR: frozenset(),
    AuthorityScopeLevel.ORDER: frozenset({
        AuthorityScopeLevel.EXECUTION,
    }),
    AuthorityScopeLevel.EXECUTION: frozenset(),
    AuthorityScopeLevel.CAPITAL: frozenset(),
    AuthorityScopeLevel.MARKET: frozenset(),
    AuthorityScopeLevel.RISK: frozenset(),
}


@dataclass
class AuthorityScope:
    """
    Defines the boundaries of a particular authority.

    An authority with PORTFOLIO scope cannot approve GLOBAL-level actions.
    Lower scopes can tighten upper constraints but cannot relax them.

    Example:
        scope: PORTFOLIO
        allowed_levels: [PORTFOLIO, STRATEGY, ORDER]
        excluded_levels: []  -- cannot touch GLOBAL or CAPITAL
    """

    scope_id: str
    level: AuthorityScopeLevel = AuthorityScopeLevel.PORTFOLIO

    # Explicitly allowed sub-scopes
    allowed_levels: List[AuthorityScopeLevel] = field(default_factory=list)

    # Explicitly excluded (even if parent)
    excluded_levels: List[AuthorityScopeLevel] = field(default_factory=list)

    # Scope identifiers
    portfolio_ids: List[str] = field(default_factory=list)
    strategy_ids: List[str] = field(default_factory=list)
    asset_ids: List[str] = field(default_factory=list)

    def covers(self, target_level: AuthorityScopeLevel) -> bool:
        """Check if this scope covers the given level."""
        if target_level in self.excluded_levels:
            return False
        if target_level == self.level:
            return True
        if target_level in self.allowed_levels:
            return True

        # Check hierarchy: can only go DOWN (more specific), not UP
        return self._is_descendant_of(target_level, self.level)

    def can_approve(self, target_level: AuthorityScopeLevel) -> bool:
        """Check if this scope can approve actions at the target level."""
        return self.covers(target_level)

    @staticmethod
    def _is_descendant_of(child: AuthorityScopeLevel, ancestor: AuthorityScopeLevel) -> bool:
        """Check if child is a descendant of ancestor in the scope hierarchy."""
        visited: set = set()
        stack = [ancestor]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if current == child:
                return True
            children = _SCOPE_HIERARCHY.get(current, frozenset())
            for c in children:
                if c not in visited:
                    stack.append(c)
        return False

    @staticmethod
    def hierarchy() -> Dict[str, List[str]]:
        """Return the scope hierarchy as a dict for visualization."""
        return {k.name: [v.name for v in vs] for k, vs in _SCOPE_HIERARCHY.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "level": self.level.name,
            "allowed_levels": [a.name for a in self.allowed_levels],
            "excluded_levels": [e.name for e in self.excluded_levels],
            "portfolio_ids": self.portfolio_ids,
            "strategy_ids": self.strategy_ids,
            "asset_ids": self.asset_ids,
        }
