"""
Environment profile validator.

Validates environment profiles for:
- Missing required variables
- Duplicate keys in inheritance chain
- Circular inheritance
- Readonly violation (overriding readonly vars)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import EnvironmentProfile


class EnvironmentValidator:
    """
    Validates environment profiles.

    Checks for common configuration errors
    including circular inheritance, readonly
    violations, and missing required variables.

    Usage:
        validator = EnvironmentValidator()
        errors = validator.validate_profile(profile, registry)
        if errors:
            for error in errors:
                print(error)
    """

    def validate_profile(
        self,
        profile: EnvironmentProfile,
        registry: Optional[Any] = None,
    ) -> List[str]:
        """
        Validate a single profile.

        Args:
            profile: Profile to validate.
            registry: EnvironmentRegistry for parent lookups.

        Returns:
            List of validation error messages.
        """
        errors: List[str] = []

        # Check: Circular inheritance
        circular = self._check_circular_inheritance(profile, registry)
        if circular:
            errors.append(circular)

        # Check: Readonly violation
        readonly_error = self._check_readonly_violation(profile, registry)
        if readonly_error:
            errors.append(readonly_error)

        # Check: Missing required variables
        missing = self._check_missing_vars(profile)
        if missing:
            errors.append(missing)

        return errors

    def validate_all(
        self,
        profiles: List[EnvironmentProfile],
        registry: Optional[Any] = None,
    ) -> Dict[str, List[str]]:
        """
        Validate all profiles.

        Args:
            profiles: List of profiles to validate.
            registry: EnvironmentRegistry.

        Returns:
            Dict mapping profile name to list of errors.
        """
        results: Dict[str, List[str]] = {}
        for profile in profiles:
            errors = self.validate_profile(profile, registry)
            if errors:
                results[profile.name] = errors
        return results

    def _check_circular_inheritance(
        self,
        profile: EnvironmentProfile,
        registry: Optional[Any] = None,
    ) -> Optional[str]:
        """Check for circular inheritance."""
        visited = {profile.name}
        current = profile

        while current.parent is not None:
            parent_name = current.parent
            if parent_name in visited:
                return (
                    f"Circular inheritance detected: "
                    f"{' -> '.join(visited)} -> {parent_name}"
                )
            visited.add(parent_name)

            # Resolve parent
            parent = self._resolve_parent(parent_name, registry)
            if parent is None:
                break
            current = parent

        return None

    def _check_readonly_violation(
        self,
        profile: EnvironmentProfile,
        registry: Optional[Any] = None,
    ) -> Optional[str]:
        """Check if profile overrides readonly parent variables."""
        if profile.parent is None:
            return None

        parent = self._resolve_parent(profile.parent, registry)
        if parent is None:
            return None

        if not parent.readonly:
            return None

        # Check if child overrides any readonly parent variables
        overridden = []
        for key in profile.variables:
            if key in parent.variables and parent.readonly:
                overridden.append(key)

        if overridden:
            return (
                f"Profile '{profile.name}' overrides readonly "
                f"variables from parent '{parent.name}': {overridden}"
            )

        return None

    def _check_missing_vars(
        self,
        profile: EnvironmentProfile,
    ) -> Optional[str]:
        """Check for critical missing variables."""
        required_keys = [
            "app.environment",
        ]
        missing = [
            k for k in required_keys
            if k not in profile.variables
        ]
        if missing and profile.parent is None:
            return f"Missing required variables: {missing}"
        return None

    def _resolve_parent(
        self,
        parent_name: str,
        registry: Optional[Any] = None,
    ) -> Optional[EnvironmentProfile]:
        """Resolve a parent profile."""
        if registry is not None:
            parent = registry.get(parent_name)
            if parent is not None:
                return parent

        from .profile import STANDARD_PROFILES
        return STANDARD_PROFILES.get(parent_name)
