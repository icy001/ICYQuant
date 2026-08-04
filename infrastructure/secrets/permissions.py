"""
Secrets permission model.

Defines the role-based permission system
for secrets operations, supporting Read,
Write, Rotate, Delete, and List actions
across Admin, Operator, Service, and
Strategy roles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class SecretAction(str, Enum):
    """Secret operations/actions."""

    READ = "read"
    WRITE = "write"
    ROTATE = "rotate"
    DELETE = "delete"
    LIST = "list"


class SecretRole(str, Enum):
    """Predefined roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    SERVICE = "service"
    STRATEGY = "strategy"


@dataclass
class RolePermissions:
    """
    Permissions for a specific role.

    Defines which actions are allowed
    for a role, with optional restrictions
    on namespaces and patterns.

    Attributes:
        role: The role name.
        allowed_actions: Set of allowed actions.
        allowed_namespaces: Set of allowed namespaces (empty = all).
        allowed_patterns: Set of allowed key patterns (empty = all).
        denied_actions: Set of explicitly denied actions.
    """

    role: SecretRole
    allowed_actions: Set[SecretAction] = field(default_factory=set)
    allowed_namespaces: Set[str] = field(default_factory=set)
    allowed_patterns: Set[str] = field(default_factory=set)
    denied_actions: Set[SecretAction] = field(default_factory=set)

    def can(self, action: SecretAction, namespace: str = "", key: str = "") -> bool:
        """
        Check if an action is allowed.

        Args:
            action: The action to check.
            namespace: Target namespace.
            key: Target secret key.

        Returns:
            True if action is allowed.
        """
        # Check denied actions
        if action in self.denied_actions:
            return False

        # Check allowed actions
        if self.allowed_actions and action not in self.allowed_actions:
            return False

        # Check namespace
        if self.allowed_namespaces and namespace not in self.allowed_namespaces:
            return False

        # Check pattern
        if self.allowed_patterns and key:
            import fnmatch
            if not any(fnmatch.fnmatch(key, p) for p in self.allowed_patterns):
                return False

        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "role": self.role.value,
            "allowed_actions": [a.value for a in self.allowed_actions],
            "allowed_namespaces": list(self.allowed_namespaces),
            "allowed_patterns": list(self.allowed_patterns),
            "denied_actions": [a.value for a in self.denied_actions],
        }


class PermissionModel:
    """
    Role-based permission model.

    Manages role permissions and provides
    access checking for secret operations.

    Usage:
        model = PermissionModel()
        model.set_role_permissions(SecretRole.ADMIN, all_permissions=True)
        allowed = model.can(SecretRole.ADMIN, SecretAction.WRITE)
    """

    def __init__(self) -> None:
        self._permissions: Dict[SecretRole, RolePermissions] = {}
        self._init_default_roles()

    def _init_default_roles(self) -> None:
        """Initialize default role permissions."""
        # Admin: full access
        self._permissions[SecretRole.ADMIN] = RolePermissions(
            role=SecretRole.ADMIN,
            allowed_actions={
                SecretAction.READ,
                SecretAction.WRITE,
                SecretAction.ROTATE,
                SecretAction.DELETE,
                SecretAction.LIST,
            },
        )

        # Operator: read, rotate, list
        self._permissions[SecretRole.OPERATOR] = RolePermissions(
            role=SecretRole.OPERATOR,
            allowed_actions={
                SecretAction.READ,
                SecretAction.ROTATE,
                SecretAction.LIST,
            },
        )

        # Service: read, list
        self._permissions[SecretRole.SERVICE] = RolePermissions(
            role=SecretRole.SERVICE,
            allowed_actions={
                SecretAction.READ,
                SecretAction.LIST,
            },
        )

        # Strategy: read only
        self._permissions[SecretRole.STRATEGY] = RolePermissions(
            role=SecretRole.STRATEGY,
            allowed_actions={
                SecretAction.READ,
            },
        )

    def can(
        self,
        role: SecretRole,
        action: SecretAction,
        namespace: str = "",
        key: str = "",
    ) -> bool:
        """
        Check if a role can perform an action.

        Args:
            role: The role.
            action: The action to check.
            namespace: Target namespace.
            key: Target secret key.

        Returns:
            True if action is allowed.
        """
        perms = self._permissions.get(role)
        if not perms:
            return False
        return perms.can(action, namespace, key)

    def get_permissions(
        self,
        role: SecretRole,
    ) -> Optional[RolePermissions]:
        """Get permissions for a role."""
        return self._permissions.get(role)

    def set_permissions(
        self,
        role: SecretRole,
        permissions: RolePermissions,
    ) -> None:
        """
        Set permissions for a role.

        Args:
            role: The role.
            permissions: New permissions.
        """
        self._permissions[role] = permissions

    def grant(
        self,
        role: SecretRole,
        action: SecretAction,
    ) -> None:
        """
        Grant an action to a role.

        Args:
            role: The role.
            action: The action to grant.
        """
        if role not in self._permissions:
            self._permissions[role] = RolePermissions(role=role)
        self._permissions[role].allowed_actions.add(action)
        self._permissions[role].denied_actions.discard(action)

    def revoke(
        self,
        role: SecretRole,
        action: SecretAction,
    ) -> None:
        """
        Revoke an action from a role.

        Args:
            role: The role.
            action: The action to revoke.
        """
        if role in self._permissions:
            self._permissions[role].allowed_actions.discard(action)
            self._permissions[role].denied_actions.add(action)

    def restrict_namespace(
        self,
        role: SecretRole,
        namespace: str,
    ) -> None:
        """
        Restrict a role to a specific namespace.

        Args:
            role: The role.
            namespace: Allowed namespace.
        """
        if role not in self._permissions:
            self._permissions[role] = RolePermissions(role=role)
        self._permissions[role].allowed_namespaces.add(namespace)

    def restrict_pattern(
        self,
        role: SecretRole,
        pattern: str,
    ) -> None:
        """
        Restrict a role to a specific key pattern.

        Args:
            role: The role.
            pattern: Allowed key pattern.
        """
        if role not in self._permissions:
            self._permissions[role] = RolePermissions(role=role)
        self._permissions[role].allowed_patterns.add(pattern)

    def list_roles(self) -> List[SecretRole]:
        """List all configured roles."""
        return list(self._permissions.keys())

    def get_all_permissions(self) -> Dict[str, Dict]:
        """Get all role permissions as dicts."""
        return {
            role.value: perms.to_dict()
            for role, perms in self._permissions.items()
        }

    def reset_role(
        self,
        role: SecretRole,
    ) -> None:
        """Reset a role to default permissions."""
        self._init_default_roles()
