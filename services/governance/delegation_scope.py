"""
Delegation Scope — defines what domain a delegation covers.

Delegation scope MUST be a subset of the original authority's scope.
Cannot expand beyond what the delegator can approve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .authority_scope import AuthorityScopeLevel


@dataclass
class DelegationScope:
    """
    Defines the boundaries of a delegated authority.

    Key constraint: delegation scope ⊆ original authority scope.
    """
    scope_id: str

    # The scope levels this delegation covers
    allowed_levels: List[AuthorityScopeLevel] = field(default_factory=list)

    # Specific identifiers (portfolio IDs, strategy IDs)
    portfolio_ids: List[str] = field(default_factory=list)
    strategy_ids: List[str] = field(default_factory=list)

    def is_subset_of(self, parent_level: AuthorityScopeLevel) -> bool:
        """Check that this delegation scope is a subset of the parent authority."""
        for level in self.allowed_levels:
            if not self._is_descendant_or_equal(level, parent_level):
                return False
        return True

    def covers(self, level: AuthorityScopeLevel) -> bool:
        """Check if this delegation scope covers the given level."""
        return level in self.allowed_levels

    @staticmethod
    def _is_descendant_or_equal(child: AuthorityScopeLevel, ancestor: AuthorityScopeLevel) -> bool:
        """Check hierarchy: child is at or below ancestor."""
        if child == ancestor:
            return True

        from .authority_scope import _SCOPE_HIERARCHY
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "allowed_levels": [l.name for l in self.allowed_levels],
            "portfolio_ids": self.portfolio_ids,
            "strategy_ids": self.strategy_ids,
        }
