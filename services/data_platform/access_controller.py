"""ICYQuant Data Access Controller.

Role-based access control (RBAC) for the data platform.
Different roles have different permissions:
    - Research: Read, Write Feature
    - Trader: Read Prediction
    - Admin: Full Access
    - Auditor: Read All (audit trail)

Usage::

    ac = AccessController(AccessControlConfig())
    ac.create_role("research", permissions=["read", "write_feature"])
    ac.assign_role("alice", "research")
    can_read = ac.check_permission("alice", "market_tick", "read")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from services.data_platform.config import (
    AccessControlConfig,
    AccessLevel,
    DataClassification,
)


# ============================================================================
# Access Control Types
# ============================================================================


@dataclass
class Role:
    """A role definition with permissions."""

    name: str
    description: str = ""
    permissions: Set[str] = field(default_factory=set)
    access_level: AccessLevel = AccessLevel.READ
    max_classification: DataClassification = DataClassification.INTERNAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permissions": sorted(self.permissions),
            "access_level": self.access_level.value,
            "max_classification": self.max_classification.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class UserAccess:
    """User access record."""

    user_id: str
    roles: List[str] = field(default_factory=list)
    granted_datasets: Dict[str, AccessLevel] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_access: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "roles": self.roles,
            "granted_datasets": {k: v.value for k, v in self.granted_datasets.items()},
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_access": self.last_access.isoformat() if self.last_access else None,
            "metadata": self.metadata,
        }


@dataclass
class AccessRequest:
    """An access request."""

    request_id: str
    user_id: str
    dataset: str
    requested_level: AccessLevel
    reason: str = ""
    status: str = "pending"  # pending, approved, denied
    requested_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessDecision:
    """Result of an access control check."""

    allowed: bool
    user_id: str
    dataset: str
    requested_action: str
    reason: str = ""
    effective_role: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# Access Controller
# ============================================================================


class AccessController:
    """Role-Based Access Controller.

    Manages roles, users, and permissions for the data platform.
    Enforces access control on every data operation.

    Usage::

        ac = AccessController()
        ac.create_role("researcher", permissions=["read", "write_feature"])
        ac.assign_role("alice", "researcher")
        decision = ac.check_permission("alice", "market_tick", "read")
        if decision.allowed:
            data = fabric.query(...)
    """

    # Standard permissions
    PERM_READ = "read"
    PERM_WRITE = "write"
    PERM_DELETE = "delete"
    PERM_ADMIN = "admin"
    PERM_WRITE_FEATURE = "write_feature"
    PERM_READ_PREDICTION = "read_prediction"
    PERM_EXPORT = "export"
    PERM_AUDIT = "audit"

    def __init__(self, config: Optional[AccessControlConfig] = None) -> None:
        self.config = config or AccessControlConfig()
        self._roles: Dict[str, Role] = {}
        self._users: Dict[str, UserAccess] = {}
        self._requests: Dict[str, AccessRequest] = {}
        self._request_counter: int = 0

        # Create default roles
        self._init_default_roles()

    def _init_default_roles(self) -> None:
        """Initialize standard roles."""
        self.create_role("admin", description="Full system access", permissions={
            self.PERM_READ, self.PERM_WRITE, self.PERM_DELETE,
            self.PERM_ADMIN, self.PERM_EXPORT, self.PERM_AUDIT,
        }, access_level=AccessLevel.ADMIN, max_classification=DataClassification.RESTRICTED)

        self.create_role("researcher", description="Research team access", permissions={
            self.PERM_READ, self.PERM_WRITE_FEATURE, self.PERM_EXPORT,
        }, access_level=AccessLevel.WRITE, max_classification=DataClassification.CONFIDENTIAL)

        self.create_role("trader", description="Trader access", permissions={
            self.PERM_READ, self.PERM_READ_PREDICTION,
        }, access_level=AccessLevel.READ, max_classification=DataClassification.CONFIDENTIAL)

        self.create_role("auditor", description="Audit access", permissions={
            self.PERM_READ, self.PERM_AUDIT,
        }, access_level=AccessLevel.READ, max_classification=DataClassification.RESTRICTED)

        self.create_role("viewer", description="Read-only access", permissions={
            self.PERM_READ,
        }, access_level=AccessLevel.READ, max_classification=DataClassification.INTERNAL)

    # ------------------------------------------------------------------
    # Role Management
    # ------------------------------------------------------------------

    def create_role(
        self,
        name: str,
        description: str = "",
        permissions: Optional[Set[str]] = None,
        access_level: AccessLevel = AccessLevel.READ,
        max_classification: DataClassification = DataClassification.INTERNAL,
    ) -> Role:
        """Create a new role.

        Args:
            name: Role name.
            description: Role description.
            permissions: Set of permission strings.
            access_level: Default access level.
            max_classification: Maximum data classification allowed.

        Returns:
            Created Role.
        """
        role = Role(
            name=name,
            description=description,
            permissions=permissions or set(),
            access_level=access_level,
            max_classification=max_classification,
        )
        self._roles[name] = role
        return role

    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)

    def list_roles(self) -> List[Role]:
        """List all roles."""
        return list(self._roles.values())

    def update_role_permissions(self, name: str, permissions: Set[str]) -> bool:
        """Update permissions for a role.

        Args:
            name: Role name.
            permissions: New permission set.

        Returns:
            True if updated.
        """
        role = self._roles.get(name)
        if not role:
            return False
        role.permissions = permissions
        return True

    # ------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------

    def register_user(self, user_id: str, **kwargs: Any) -> UserAccess:
        """Register a new user.

        Args:
            user_id: User identifier.
            **kwargs: Additional metadata.

        Returns:
            UserAccess record.
        """
        user = UserAccess(user_id=user_id, metadata=kwargs)
        self._users[user_id] = user
        return user

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User identifier.
            role_name: Role to assign.

        Returns:
            True if assigned.

        Raises:
            ValueError: If role doesn't exist.
        """
        if role_name not in self._roles:
            raise ValueError(f"Role '{role_name}' does not exist")

        user = self._users.get(user_id)
        if not user:
            user = self.register_user(user_id)

        if len(user.roles) >= self.config.max_roles_per_user:
            raise ValueError(
                f"User '{user_id}' has max roles ({self.config.max_roles_per_user})"
            )

        if role_name not in user.roles:
            user.roles.append(role_name)

        return True

    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """Revoke a role from a user.

        Args:
            user_id: User identifier.
            role_name: Role to revoke.

        Returns:
            True if revoked.
        """
        user = self._users.get(user_id)
        if not user or role_name not in user.roles:
            return False
        user.roles.remove(role_name)
        return True

    def grant_dataset_access(
        self, user_id: str, dataset: str, level: AccessLevel
    ) -> bool:
        """Grant specific dataset access to a user.

        Args:
            user_id: User identifier.
            dataset: Dataset name.
            level: Access level.

        Returns:
            True if granted.
        """
        user = self._users.get(user_id)
        if not user:
            user = self.register_user(user_id)

        user.granted_datasets[dataset] = level
        return True

    def get_user(self, user_id: str) -> Optional[UserAccess]:
        """Get a user's access record."""
        return self._users.get(user_id)

    def list_users(self) -> List[UserAccess]:
        """List all users."""
        return list(self._users.values())

    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all effective permissions for a user.

        Args:
            user_id: User identifier.

        Returns:
            Set of all permission strings from all roles.
        """
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return set()

        permissions: Set[str] = set()
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if role:
                permissions.update(role.permissions)

        return permissions

    # ------------------------------------------------------------------
    # Permission Checking
    # ------------------------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        dataset: str,
        action: str,
        classification: Optional[DataClassification] = None,
    ) -> AccessDecision:
        """Check if a user has permission for an action.

        Args:
            user_id: User identifier.
            dataset: Dataset name.
            action: Action to check (e.g. "read", "write").
            classification: Data classification (if known).

        Returns:
            AccessDecision with allowed/reason.
        """
        user = self._users.get(user_id)

        # User must exist and be active
        if not user:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                dataset=dataset,
                requested_action=action,
                reason=f"User '{user_id}' not found",
            )

        if not user.is_active:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                dataset=dataset,
                requested_action=action,
                reason=f"User '{user_id}' is inactive",
            )

        # Check dataset-specific grants first
        if dataset in user.granted_datasets:
            granted_level = user.granted_datasets[dataset]
            required_level = self._action_to_level(action)

            if granted_level.value >= required_level.value:
                user.last_access = datetime.utcnow()
                return AccessDecision(
                    allowed=True,
                    user_id=user_id,
                    dataset=dataset,
                    requested_action=action,
                    reason=f"Direct grant: {granted_level.value}",
                    effective_role="direct_grant",
                )

        # Check role-based permissions
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if not role:
                continue

            # Check if role has the required permission
            if action in role.permissions:
                # Check classification constraint
                if classification:
                    if self._classification_level(classification) > self._classification_level(role.max_classification):
                        continue

                user.last_access = datetime.utcnow()
                return AccessDecision(
                    allowed=True,
                    user_id=user_id,
                    dataset=dataset,
                    requested_action=action,
                    reason=f"Role '{role_name}' grants '{action}'",
                    effective_role=role_name,
                )

        # Check if any role has admin permission
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if role and self.PERM_ADMIN in role.permissions:
                user.last_access = datetime.utcnow()
                return AccessDecision(
                    allowed=True,
                    user_id=user_id,
                    dataset=dataset,
                    requested_action=action,
                    reason=f"Role '{role_name}' has admin access",
                    effective_role=role_name,
                )

        return AccessDecision(
            allowed=False,
            user_id=user_id,
            dataset=dataset,
            requested_action=action,
            reason=f"No permission for '{action}' on '{dataset}'",
        )

    def _action_to_level(self, action: str) -> AccessLevel:
        """Map an action to the required access level."""
        mapping = {
            self.PERM_READ: AccessLevel.READ,
            self.PERM_EXPORT: AccessLevel.READ,
            self.PERM_AUDIT: AccessLevel.READ,
            self.PERM_READ_PREDICTION: AccessLevel.READ,
            self.PERM_WRITE: AccessLevel.WRITE,
            self.PERM_WRITE_FEATURE: AccessLevel.WRITE,
            self.PERM_DELETE: AccessLevel.ADMIN,
            self.PERM_ADMIN: AccessLevel.ADMIN,
        }
        return mapping.get(action, AccessLevel.READ)

    @staticmethod
    def _classification_level(cls: DataClassification) -> int:
        """Get numeric level for classification comparison."""
        levels = {
            DataClassification.PUBLIC: 0,
            DataClassification.INTERNAL: 1,
            DataClassification.CONFIDENTIAL: 2,
            DataClassification.RESTRICTED: 3,
        }
        return levels.get(cls, 1)

    # ------------------------------------------------------------------
    # Access Requests
    # ------------------------------------------------------------------

    def request_access(
        self,
        user_id: str,
        dataset: str,
        level: AccessLevel,
        reason: str = "",
    ) -> AccessRequest:
        """Submit an access request.

        Args:
            user_id: Requesting user.
            dataset: Dataset name.
            level: Requested access level.
            reason: Justification.

        Returns:
            AccessRequest.
        """
        self._request_counter += 1
        request = AccessRequest(
            request_id=f"req_{self._request_counter}",
            user_id=user_id,
            dataset=dataset,
            requested_level=level,
            reason=reason,
        )
        self._requests[request.request_id] = request
        return request

    def approve_request(self, request_id: str, approved_by: str) -> bool:
        """Approve an access request and grant access.

        Args:
            request_id: Request ID.
            approved_by: Approver identifier.

        Returns:
            True if approved and granted.
        """
        request = self._requests.get(request_id)
        if not request or request.status != "pending":
            return False

        request.status = "approved"
        request.resolved_at = datetime.utcnow()
        request.resolved_by = approved_by

        # Grant access
        return self.grant_dataset_access(
            request.user_id, request.dataset, request.requested_level
        )

    def deny_request(self, request_id: str, denied_by: str) -> bool:
        """Deny an access request.

        Args:
            request_id: Request ID.
            denied_by: Denier identifier.

        Returns:
            True if denied.
        """
        request = self._requests.get(request_id)
        if not request or request.status != "pending":
            return False

        request.status = "denied"
        request.resolved_at = datetime.utcnow()
        request.resolved_by = denied_by
        return True

    def list_pending_requests(self) -> List[AccessRequest]:
        """List all pending access requests."""
        return [r for r in self._requests.values() if r.status == "pending"]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_access_stats(self) -> Dict[str, Any]:
        """Get access control statistics."""
        return {
            "total_users": len(self._users),
            "active_users": sum(1 for u in self._users.values() if u.is_active),
            "total_roles": len(self._roles),
            "pending_requests": len(self.list_pending_requests()),
            "roles_summary": {
                name: len([
                    u for u in self._users.values()
                    if name in u.roles
                ])
                for name in self._roles
            },
        }

    def audit_user_access(self, user_id: str) -> Dict[str, Any]:
        """Get a comprehensive access audit for a user.

        Args:
            user_id: User identifier.

        Returns:
            Dict with permissions, roles, and grants.
        """
        user = self._users.get(user_id)
        if not user:
            return {"error": f"User '{user_id}' not found"}

        return {
            "user_id": user_id,
            "is_active": user.is_active,
            "roles": user.roles,
            "effective_permissions": sorted(self.get_user_permissions(user_id)),
            "dataset_grants": {
                k: v.value for k, v in user.granted_datasets.items()
            },
            "last_access": user.last_access.isoformat() if user.last_access else None,
        }
