"""
Profile inheritance.

Implements profile inheritance with merge
strategies: recursive merge, override, and
list replacement.

Inheritance hierarchy:
    base
    ├── development
    ├── testing
    ├── staging
    └── production

A child profile inherits all variables from
its parent, then applies its own overrides.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import EnvironmentProfile


class ProfileInheritance:
    """
    Merges profiles through inheritance.

    Resolves the full variable set for a profile
    by walking up the inheritance chain and merging
    variables at each level.

    Merge Strategies:
    - recursive: Deep merge nested dicts
    - override: Child values completely override parent
    - list_replace: Lists are replaced (not merged)
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
    ) -> None:
        """
        Initialize inheritance resolver.

        Args:
            registry: EnvironmentRegistry for profile lookups.
        """
        self._registry = registry

    def resolve(
        self,
        profile: EnvironmentProfile,
    ) -> Dict[str, Any]:
        """
        Resolve full inherited variables for a profile.

        Walks up the inheritance chain from the given
        profile through all parent profiles, merging
        variables at each level.

        Args:
            profile: Starting profile.

        Returns:
            Dict of all resolved variables.
        """
        chain = self._build_chain(profile)
        result: Dict[str, Any] = {}

        # Merge from root (base) to leaf (child)
        for p in reversed(chain):
            result = self._merge_two(result, p.variables)

        return result

    def _build_chain(
        self,
        profile: EnvironmentProfile,
    ) -> List[EnvironmentProfile]:
        """
        Build the inheritance chain from leaf to root.

        Returns a list of profiles from the given
        profile up to the base profile.

        Args:
            profile: Starting profile.

        Returns:
            List of profiles in inheritance order.
        """
        chain = [profile]
        visited = {profile.name}

        current = profile
        while current.parent is not None:
            parent_name = current.parent
            if parent_name in visited:
                # Circular inheritance detected
                break
            visited.add(parent_name)

            parent = self._resolve_parent(parent_name)
            if parent is None:
                break
            chain.append(parent)
            current = parent

        return chain

    def _resolve_parent(
        self,
        parent_name: str,
    ) -> EnvironmentProfile:
        """Resolve a parent profile by name."""
        if self._registry is not None:
            parent = self._registry.get(parent_name)
            if parent is not None:
                return parent

        # Try to import from standard profiles
        from .profile import STANDARD_PROFILES
        if parent_name in STANDARD_PROFILES:
            return STANDARD_PROFILES[parent_name]

        # Fall back to base
        from .profile import BASE_PROFILE
        return BASE_PROFILE

    def _merge_two(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge two variable dictionaries.

        Uses recursive merge: nested dicts are
        merged, other values are overridden.

        Args:
            base: Base variables.
            override: Override variables.

        Returns:
            Merged variables.
        """
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_two(result[key], value)
            else:
                result[key] = value
        return result
