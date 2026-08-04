"""
Secrets access policy.

Provides the framework for defining
and enforcing access policies on secrets,
supporting least privilege, read-only,
namespace isolation, and tenant isolation
models.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .constants import AccessLevel
from .exceptions import SecretAccessDeniedError, SecretPolicyError

logger = logging.getLogger(__name__)


@dataclass
class AccessRule:
    """
    A single access rule.

    Defines access permissions for a specific
    pattern of secrets and roles.

    Attributes:
        pattern: Glob pattern for secret keys (e.g., "db/*", "*").
        namespace: Namespace restriction.
        roles: Set of roles allowed access.
        level: Minimum access level required.
        readonly: If True, only read access is allowed.
        ttl: Cache TTL for access decisions.
        enabled: Whether this rule is active.
    """

    pattern: str = "*"
    namespace: str = "*"
    roles: Set[str] = field(default_factory=set)
    level: AccessLevel = AccessLevel.READ
    readonly: bool = False
    ttl: int = 0
    enabled: bool = True


class SecretAccessPolicy:
    """
    Secret access policy engine.

    Defines and enforces access policies for
    secrets, supporting least privilege,
    read-only, namespace isolation, and
    tenant isolation.

    Usage:
        policy = SecretAccessPolicy()
        policy.add_rule(AccessRule(pattern="db/*", roles={"service"}))
        allowed = policy.check_access("db/password", "service", AccessLevel.READ)
    """

    def __init__(self) -> None:
        self._rules: List[AccessRule] = []
        self._default_level = AccessLevel.NONE
        self._enforce_ns_isolation = True
        self._enforce_least_privilege = True
        # Cached decisions: (key, role, level) -> allowed
        self._decision_cache: Dict[tuple, bool] = {}

    # ── Rule Management ──

    def add_rule(
        self,
        rule: AccessRule,
    ) -> None:
        """
        Add an access rule.

        Args:
            rule: The access rule to add.
        """
        self._rules.append(rule)
        self._decision_cache.clear()

    def remove_rule(
        self,
        pattern: str,
        namespace: str = "*",
    ) -> int:
        """
        Remove rules matching pattern and namespace.

        Args:
            pattern: Glob pattern to match.
            namespace: Namespace to match.

        Returns:
            Number of rules removed.
        """
        count = 0
        new_rules = []
        for rule in self._rules:
            if fnmatch.fnmatch(rule.pattern, pattern) and rule.namespace == namespace:
                count += 1
            else:
                new_rules.append(rule)

        self._rules = new_rules
        self._decision_cache.clear()
        return count

    def clear_rules(self) -> None:
        """Remove all rules."""
        self._rules.clear()
        self._decision_cache.clear()

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all rules as dicts."""
        return [
            {
                "pattern": r.pattern,
                "namespace": r.namespace,
                "roles": list(r.roles),
                "level": r.level.value,
                "readonly": r.readonly,
                "enabled": r.enabled,
            }
            for r in self._rules
        ]

    # ── Predefined Policies ──

    def add_least_privilege_policy(self) -> None:
        """Add least privilege policy - only specific grants allowed."""
        self._rules.clear()
        self._default_level = AccessLevel.NONE
        self._decision_cache.clear()

    def add_readonly_policy(
        self,
        roles: Optional[Set[str]] = None,
    ) -> None:
        """
        Add a read-only policy.

        Args:
            roles: Roles with read-only access.
        """
        self.add_rule(
            AccessRule(
                pattern="*",
                namespace="*",
                roles=roles or {"service", "strategy", "operator"},
                level=AccessLevel.READ,
                readonly=True,
            )
        )

    def add_admin_policy(
        self,
        roles: Optional[Set[str]] = None,
    ) -> None:
        """
        Add admin-level access for specified roles.

        Args:
            roles: Roles with admin access.
        """
        self.add_rule(
            AccessRule(
                pattern="*",
                namespace="*",
                roles=roles or {"admin"},
                level=AccessLevel.ADMIN,
                readonly=False,
            )
        )

    def add_namespace_isolation_policy(
        self,
        namespace: str,
        allowed_roles: Set[str],
    ) -> None:
        """
        Add namespace isolation policy.

        Only specified roles can access secrets
        in this namespace.

        Args:
            namespace: Namespace to isolate.
            allowed_roles: Roles with access.
        """
        self.add_rule(
            AccessRule(
                pattern="*",
                namespace=namespace,
                roles=allowed_roles,
                level=AccessLevel.READ,
                readonly=False,
            )
        )

    # ── Access Checking ──

    def check_access(
        self,
        key: str,
        role: str,
        level: AccessLevel = AccessLevel.READ,
        namespace: str = "default",
    ) -> bool:
        """
        Check if a role has access to a secret.

        Args:
            key: The secret key.
            role: The requesting role.
            level: Required access level.
            namespace: Namespace.

        Returns:
            True if access is allowed.
        """
        cache_key = (key, role, level.value, namespace)
        if cache_key in self._decision_cache:
            return self._decision_cache[cache_key]

        allowed = self._evaluate_rules(key, role, level, namespace)
        self._decision_cache[cache_key] = allowed
        return allowed

    def enforce_access(
        self,
        key: str,
        role: str,
        level: AccessLevel = AccessLevel.READ,
        namespace: str = "default",
    ) -> None:
        """
        Enforce access - raise if denied.

        Args:
            key: The secret key.
            role: The requesting role.
            level: Required access level.
            namespace: Namespace.

        Raises:
            SecretAccessDeniedError: If access denied.
        """
        if not self.check_access(key, role, level, namespace):
            raise SecretAccessDeniedError(
                key=key,
                role=role,
                reason=f"Required level: {level.value}",
            )

    def _evaluate_rules(
        self,
        key: str,
        role: str,
        level: AccessLevel,
        namespace: str,
    ) -> bool:
        """Evaluate all rules for an access request."""
        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check namespace match
            if rule.namespace != "*" and not fnmatch.fnmatch(namespace, rule.namespace):
                continue

            # Check pattern match
            if not fnmatch.fnmatch(key, rule.pattern):
                continue

            # Check role
            if rule.roles and role not in rule.roles:
                continue

            # Check level
            if level.value > rule.level.value:
                continue

            # Check readonly
            if rule.readonly and level.value > AccessLevel.READ.value:
                continue

            return True

        return False

    def get_effective_permissions(
        self,
        role: str,
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        Get effective permissions for a role in a namespace.

        Args:
            role: The role name.
            namespace: The namespace.

        Returns:
            List of effective rules.
        """
        permissions = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.namespace != "*" and rule.namespace != namespace:
                continue
            if rule.roles and role not in rule.roles:
                continue

            permissions.append({
                "pattern": rule.pattern,
                "level": rule.level.value,
                "readonly": rule.readonly,
            })

        return permissions

    def get_stats(self) -> Dict[str, Any]:
        """Get policy statistics."""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "decision_cache_size": len(self._decision_cache),
            "default_level": self._default_level.value,
        }
