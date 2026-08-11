"""
ICYQuant Permission Manager — role-based permission management for data platform.

Manages users, roles, and role assignments with hierarchical roles
and dataset-level permission granularity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    DATASET_DELETE = "dataset:delete"
    DATASET_ADMIN = "dataset:admin"
    CATALOG_READ = "catalog:read"
    CATALOG_MANAGE = "catalog:manage"
    SCHEMA_READ = "schema:read"
    SCHEMA_MANAGE = "schema:manage"
    PIPELINE_READ = "pipeline:read"
    PIPELINE_EXECUTE = "pipeline:execute"
    PIPELINE_MANAGE = "pipeline:manage"
    GOVERNANCE_READ = "governance:read"
    GOVERNANCE_MANAGE = "governance:manage"
    API_ACCESS = "api:access"
    AUDIT_READ = "audit:read"
    ADMIN = "admin"


@dataclass
class Role:
    """A role with a set of permissions."""
    role_id: str
    name: str
    description: str = ""
    permissions: set[Permission] = field(default_factory=set)
    parent_role_id: str = ""  # Hierarchy support
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class User:
    """A user in the permission system."""
    user_id: str
    name: str = ""
    email: str = ""
    roles: list[str] = field(default_factory=list)  # role_ids
    direct_permissions: set[Permission] = field(default_factory=set)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class PermissionManager:
    """Role-based permission manager.

    Supports:
        - Role CRUD with permission sets
        - User CRUD with role assignment
        - Hierarchical roles (parent-child)
        - Direct permission grants on users
        - Permission resolution (role hierarchy flattening)
    """

    # Pre-defined roles
    ADMIN_ROLE = "admin"
    RESEARCHER_ROLE = "researcher"
    ANALYST_ROLE = "analyst"
    VIEWER_ROLE = "viewer"

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._roles: dict[str, Role] = {}
        self._register_default_roles()

    def _register_default_roles(self) -> None:
        """Register built-in roles."""
        self.create_role(Role(
            role_id=self.ADMIN_ROLE,
            name="Administrator",
            description="Full platform access",
            permissions={
                Permission.ADMIN,
                Permission.DATASET_ADMIN,
                Permission.CATALOG_MANAGE,
                Permission.SCHEMA_MANAGE,
                Permission.PIPELINE_MANAGE,
                Permission.GOVERNANCE_MANAGE,
                Permission.AUDIT_READ,
            },
        ))
        self.create_role(Role(
            role_id=self.RESEARCHER_ROLE,
            name="Researcher",
            description="Research and analysis access",
            permissions={
                Permission.DATASET_READ,
                Permission.DATASET_WRITE,
                Permission.CATALOG_READ,
                Permission.SCHEMA_READ,
                Permission.PIPELINE_READ,
                Permission.PIPELINE_EXECUTE,
                Permission.GOVERNANCE_READ,
                Permission.API_ACCESS,
            },
        ))
        self.create_role(Role(
            role_id=self.ANALYST_ROLE,
            name="Analyst",
            description="Read-only analysis access",
            permissions={
                Permission.DATASET_READ,
                Permission.CATALOG_READ,
                Permission.SCHEMA_READ,
                Permission.PIPELINE_READ,
                Permission.API_ACCESS,
            },
        ))
        self.create_role(Role(
            role_id=self.VIEWER_ROLE,
            name="Viewer",
            description="Minimal read-only access",
            permissions={
                Permission.DATASET_READ,
                Permission.CATALOG_READ,
            },
        ))

    def create_role(self, role: Role) -> str:
        """Create or update a role."""
        self._roles[role.role_id] = role
        logger.info("Role created: %s", role.role_id)
        return role.role_id

    def get_role(self, role_id: str) -> Optional[Role]:
        return self._roles.get(role_id)

    def delete_role(self, role_id: str) -> bool:
        if role_id in (self.ADMIN_ROLE, self.VIEWER_ROLE):
            return False  # Cannot delete built-in roles
        if role_id in self._roles:
            del self._roles[role_id]
            # Remove from users
            for user in self._users.values():
                user.roles = [r for r in user.roles if r != role_id]
            return True
        return False

    def create_user(self, user: User) -> str:
        """Create or update a user."""
        self._users[user.user_id] = user
        logger.info("User created: %s", user.user_id)
        return user.user_id

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def assign_role(self, user_id: str, role_id: str) -> bool:
        """Assign a role to a user."""
        user = self._users.get(user_id)
        role = self._roles.get(role_id)
        if user is None or role is None:
            return False
        if role_id not in user.roles:
            user.roles.append(role_id)
        return True

    def revoke_role(self, user_id: str, role_id: str) -> bool:
        """Revoke a role from a user."""
        user = self._users.get(user_id)
        if user is None:
            return False
        user.roles = [r for r in user.roles if r != role_id]
        return True

    def grant_permission(self, user_id: str, permission: Permission) -> bool:
        """Grant a direct permission to a user."""
        user = self._users.get(user_id)
        if user is None:
            return False
        user.direct_permissions.add(permission)
        return True

    def revoke_permission(self, user_id: str, permission: Permission) -> bool:
        """Revoke a direct permission from a user."""
        user = self._users.get(user_id)
        if user is None:
            return False
        user.direct_permissions.discard(permission)
        return True

    def get_effective_permissions(self, user_id: str) -> set[Permission]:
        """Resolve all permissions for a user (roles + direct)."""
        user = self._users.get(user_id)
        if user is None:
            return set()

        if not user.enabled:
            return set()

        permissions: set[Permission] = set(user.direct_permissions)

        # Collect from roles (including parent hierarchy)
        for role_id in user.roles:
            self._collect_role_permissions(role_id, permissions, visited=set())

        # ADMIN role grants all permissions
        if Permission.ADMIN in permissions:
            permissions.update(Permission)

        return permissions

    def _collect_role_permissions(
        self,
        role_id: str,
        permissions: set[Permission],
        visited: set[str],
    ) -> None:
        """Recursively collect permissions from a role hierarchy."""
        if role_id in visited:
            return
        visited.add(role_id)

        role = self._roles.get(role_id)
        if role:
            permissions.update(role.permissions)
            if role.parent_role_id:
                self._collect_role_permissions(role.parent_role_id, permissions, visited)

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        return permission in self.get_effective_permissions(user_id)

    def disable_user(self, user_id: str) -> bool:
        """Disable a user account."""
        user = self._users.get(user_id)
        if user is None:
            return False
        user.enabled = False
        return True

    def enable_user(self, user_id: str) -> bool:
        """Enable a user account."""
        user = self._users.get(user_id)
        if user is None:
            return False
        user.enabled = True
        return True

    @property
    def user_count(self) -> int:
        return len(self._users)

    @property
    def role_count(self) -> int:
        return len(self._roles)
