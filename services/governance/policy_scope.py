"""
Policy Scope — extended scope model with hierarchy, inheritance, and pattern matching.

Extends the original PolicyScope constants with:
  - MARKET scope
  - Hierarchical scope resolution (GLOBAL > MARKET > PORTFOLIO > STRATEGY > ORDER)
  - Pattern-matching for wildcard and regex scopes
  - Scope inclusion/exclusion sets
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Pattern, Set, Tuple


# ---------------------------------------------------------------------------
# Scope constants (extending original PolicyScope)
# ---------------------------------------------------------------------------

class PolicyScopeConstants:
    """All supported governance scope constants."""

    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    MARKET = "MARKET"
    PORTFOLIO = "PORTFOLIO"
    STRATEGY = "STRATEGY"
    ASSET = "ASSET"
    FACTOR = "FACTOR"
    ORDER = "ORDER"
    EXECUTION = "EXECUTION"
    CAPITAL = "CAPITAL"
    RISK = "RISK"

    @classmethod
    def all_scopes(cls) -> FrozenSet[str]:
        return frozenset({
            cls.GLOBAL, cls.ACCOUNT, cls.MARKET, cls.PORTFOLIO,
            cls.STRATEGY, cls.ASSET, cls.FACTOR, cls.ORDER,
            cls.EXECUTION, cls.CAPITAL, cls.RISK,
        })


# ---------------------------------------------------------------------------
# Scope hierarchy
# ---------------------------------------------------------------------------

class ScopeHierarchy:
    """
    Defines the inheritance hierarchy for scopes.

    A policy scoped to GLOBAL applies to everything.
    A policy scoped to PORTFOLIO also applies to STRATEGY, ASSET, ORDER.
    A policy scoped to ACCOUNT applies to everything under that account.

    Hierarchy (top-down, most broad first):
      GLOBAL
        ├── ACCOUNT
        │   ├── PORTFOLIO
        │   │   ├── STRATEGY
        │   │   │   ├── ASSET
        │   │   │   └── ORDER
        │   │   └── EXECUTION
        │   ├── CAPITAL
        │   └── RISK
        └── MARKET
            └── ASSET
    """

    # Map: parent scope -> set of child scopes
    CHILDREN: Dict[str, FrozenSet[str]] = {
        PolicyScopeConstants.GLOBAL: frozenset({
            PolicyScopeConstants.ACCOUNT,
            PolicyScopeConstants.MARKET,
            PolicyScopeConstants.CAPITAL,
            PolicyScopeConstants.RISK,
        }),
        PolicyScopeConstants.ACCOUNT: frozenset({
            PolicyScopeConstants.PORTFOLIO,
            PolicyScopeConstants.CAPITAL,
            PolicyScopeConstants.RISK,
        }),
        PolicyScopeConstants.MARKET: frozenset({
            PolicyScopeConstants.ASSET,
        }),
        PolicyScopeConstants.PORTFOLIO: frozenset({
            PolicyScopeConstants.STRATEGY,
            PolicyScopeConstants.EXECUTION,
        }),
        PolicyScopeConstants.STRATEGY: frozenset({
            PolicyScopeConstants.ASSET,
            PolicyScopeConstants.FACTOR,
            PolicyScopeConstants.ORDER,
        }),
        PolicyScopeConstants.ASSET: frozenset(),
        PolicyScopeConstants.FACTOR: frozenset(),
        PolicyScopeConstants.ORDER: frozenset(),
        PolicyScopeConstants.EXECUTION: frozenset(),
        PolicyScopeConstants.CAPITAL: frozenset(),
        PolicyScopeConstants.RISK: frozenset(),
    }

    # Map: child scope -> set of ancestor scopes (including itself)
    _ANCESTORS_CACHE: Dict[str, FrozenSet[str]] = {}

    @classmethod
    def is_descendant(cls, candidate: str, ancestor: str) -> bool:
        """Check if `candidate` scope is a descendant of `ancestor` scope."""
        if candidate == ancestor:
            return True
        if ancestor == PolicyScopeConstants.GLOBAL:
            return True
        ancestors = cls.get_ancestors(candidate)
        return ancestor in ancestors

    @classmethod
    def get_ancestors(cls, scope: str) -> FrozenSet[str]:
        """Return all ancestor scopes up to GLOBAL (inclusive of self)."""
        if scope in cls._ANCESTORS_CACHE:
            return cls._ANCESTORS_CACHE[scope]

        ancestors: Set[str] = {scope}
        # Walk up from scope to find all parents
        to_check = {scope}
        while to_check:
            current = to_check.pop()
            for parent, children in cls.CHILDREN.items():
                if current in children and parent not in ancestors:
                    ancestors.add(parent)
                    to_check.add(parent)

        result = frozenset(ancestors)
        cls._ANCESTORS_CACHE[scope] = result
        return result

    @classmethod
    def get_children(cls, scope: str) -> FrozenSet[str]:
        """Return direct child scopes."""
        return cls.CHILDREN.get(scope, frozenset())

    @classmethod
    def get_descendants(cls, scope: str) -> FrozenSet[str]:
        """Return all descendant scopes (transitive)."""
        result: Set[str] = set()
        stack = [scope]
        while stack:
            current = stack.pop()
            for child in cls.CHILDREN.get(current, frozenset()):
                if child not in result:
                    result.add(child)
                    stack.append(child)
        return frozenset(result)

    @classmethod
    def most_specific_common(cls, scope_a: str, scope_b: str) -> Optional[str]:
        """Find the most specific common ancestor of two scopes."""
        ancestors_a = cls.get_ancestors(scope_a)
        ancestors_b = cls.get_ancestors(scope_b)
        common = ancestors_a & ancestors_b

        if not common:
            return None

        # The most specific = lowest in hierarchy = least children
        best = None
        best_depth = -1
        for s in common:
            depth = len(cls.get_ancestors(s))
            if depth > best_depth:
                best_depth = depth
                best = s
        return best


# ---------------------------------------------------------------------------
# Extended PolicyScope
# ---------------------------------------------------------------------------

@dataclass
class PolicyScope:
    """
    An extended policy scope with hierarchy awareness and pattern matching.

    Supports:
      - Exact scope matching (GLOBAL, PORTFOLIO, etc.)
      - Hierarchical inheritance (PORTFOLIO covers STRATEGY, ASSET, ORDER)
      - Wildcard patterns (e.g., "STRATEGY:*")
      - Inclusion / exclusion sets
      - Custom matchers via callable
    """

    # Primary scope identifier
    scope: str = PolicyScopeConstants.GLOBAL

    # Scope qualifier (e.g., specific account ID, strategy name)
    qualifier: str = ""

    # Optional pattern matching (regex for scope qualifier matching)
    qualifier_pattern: Optional[str] = None

    # Fine-grained inclusion set
    include_scopes: List[str] = field(default_factory=list)

    # Fine-grained exclusion set (takes precedence over include)
    exclude_scopes: List[str] = field(default_factory=list)

    # Whether this scope inherits to descendant scopes
    inherit: bool = True

    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    _compiled_pattern: Optional[Pattern] = field(default=None, repr=False, init=False)

    # ------------------------------------------------------------------
    # Scope matching
    # ------------------------------------------------------------------

    def applies_to(self, target_scope: str, target_qualifier: str = "", *,
                   allow_inheritance: bool = True) -> bool:
        """
        Check if this policy scope applies to a given target.

        Args:
            target_scope: The scope to check against (e.g., "STRATEGY").
            target_qualifier: Optional qualifier (e.g., strategy name).
            allow_inheritance: If True, hierarchical inheritance is considered.

        Returns:
            True if this scope covers the target.
        """
        # Explicit exclusion overrides everything
        if target_scope in self.exclude_scopes:
            return False
        if target_qualifier and self.qualifier:
            # If qualifier is set, it must match
            if not self._qualifier_matches(target_qualifier):
                return False

        # Exact match (including include_scopes)
        if target_scope == self.scope or target_scope in self.include_scopes:
            return True

        # Hierarchical inheritance
        if self.inherit and allow_inheritance:
            if ScopeHierarchy.is_descendant(target_scope, self.scope):
                return True

        # GLOBAL always applies
        if self.scope == PolicyScopeConstants.GLOBAL:
            return True

        return False

    def applies_to_any(self, target_scopes: List[str], **kwargs) -> bool:
        """Check if this scope applies to any of the given target scopes."""
        return any(self.applies_to(ts, **kwargs) for ts in target_scopes)

    def applies_to_all(self, target_scopes: List[str], **kwargs) -> bool:
        """Check if this scope applies to all given target scopes."""
        return all(self.applies_to(ts, **kwargs) for ts in target_scopes)

    # ------------------------------------------------------------------
    # Qualifier matching
    # ------------------------------------------------------------------

    def _qualifier_matches(self, target_qualifier: str) -> bool:
        """Check if the target qualifier matches our qualifier or pattern."""
        if not self.qualifier and not self.qualifier_pattern:
            return True  # No qualifier restriction

        if self.qualifier:
            if target_qualifier == self.qualifier:
                return True
            # Simple wildcard support: "prefix:*"
            if self.qualifier.endswith(":*"):
                prefix = self.qualifier[:-2]
                if target_qualifier.startswith(prefix):
                    return True

        if self.qualifier_pattern:
            if self._compiled_pattern is None:
                self._compiled_pattern = re.compile(self.qualifier_pattern)
            if self._compiled_pattern.match(target_qualifier):
                return True

        return False

    @property
    def effective_scopes(self) -> List[str]:
        """Return all scopes this policy covers (self + inherited children)."""
        result = {self.scope}
        result.update(self.include_scopes)
        if self.inherit:
            result.update(ScopeHierarchy.get_descendants(self.scope))
        # Remove exclusions
        result.difference_update(self.exclude_scopes)
        return sorted(result)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope,
            "qualifier": self.qualifier,
            "qualifier_pattern": self.qualifier_pattern,
            "include_scopes": self.include_scopes,
            "exclude_scopes": self.exclude_scopes,
            "inherit": self.inherit,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyScope":
        return cls(
            scope=data.get("scope", PolicyScopeConstants.GLOBAL),
            qualifier=data.get("qualifier", ""),
            qualifier_pattern=data.get("qualifier_pattern"),
            include_scopes=data.get("include_scopes", []),
            exclude_scopes=data.get("exclude_scopes", []),
            inherit=data.get("inherit", True),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def global_scope(cls) -> "PolicyScope":
        """Convenience: scope that applies to everything."""
        return cls(scope=PolicyScopeConstants.GLOBAL)

    @classmethod
    def for_scope(cls, scope: str, qualifier: str = "") -> "PolicyScope":
        """Convenience: scope targeting a specific scope."""
        return cls(scope=scope, qualifier=qualifier)

    def __hash__(self) -> int:
        return hash((
            self.scope,
            self.qualifier,
            self.qualifier_pattern,
            tuple(sorted(self.include_scopes)),
            tuple(sorted(self.exclude_scopes)),
        ))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PolicyScope):
            return NotImplemented
        return (
            self.scope == other.scope
            and self.qualifier == other.qualifier
            and self.qualifier_pattern == other.qualifier_pattern
            and sorted(self.include_scopes) == sorted(other.include_scopes)
            and sorted(self.exclude_scopes) == sorted(other.exclude_scopes)
        )
