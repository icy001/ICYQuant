"""Registry — in-memory governance registry (Commit 28 Part 1.1).

第一版采用简单内存 Registry。后续可以接 PostgreSQL / IAM /
Policy Store / Configuration Service。
"""

from __future__ import annotations

from .models import Principal
from .permission import Permission, build_standard_permissions
from .policy import Policy
from .role import Role, STANDARD_ROLE_PERMISSIONS, build_standard_roles


def build_standard_policies() -> tuple[Policy, ...]:
    """Build the first batch of standard production governance policies.

    Priority: smaller number means higher priority (Commit 28 Part 1.1, section 24).
        10  -> Emergency Kill Policy
        50  -> Production Control Policy
    """
    return (
        Policy(
            policy_id="POLICY-TRADING-KILL-001",
            name="Emergency Trading Kill",
            resource="trading",
            action="kill",
            priority=10,
        ),
        Policy(
            policy_id="POLICY-TRADING-PAUSE-001",
            name="Production Trading Pause",
            resource="trading",
            action="pause",
            priority=50,
        ),
        Policy(
            policy_id="POLICY-TRADING-RESUME-001",
            name="Production Trading Resume",
            resource="trading",
            action="resume",
            priority=50,
        ),
        Policy(
            policy_id="POLICY-TRADING-FAILOVER-001",
            name="Production Venue Failover",
            resource="trading",
            action="failover",
            priority=50,
        ),
    )


class GovernanceRegistry:
    """Simple in-memory registry for principals, roles, permissions and policies."""

    def __init__(self) -> None:
        self._principals: dict[str, Principal] = {}
        self._roles: dict[str, Role] = {}
        self._permissions: dict[str, Permission] = {}
        self._policies: dict[str, Policy] = {}
        self._role_permissions: dict[str, set[str]] = {}

    # ---- principals ----
    def register_principal(self, principal: Principal) -> None:
        self._principals[principal.principal_id] = principal

    def get_principal(self, principal_id: str) -> Principal | None:
        return self._principals.get(principal_id)

    @property
    def principals(self) -> dict[str, Principal]:
        return dict(self._principals)

    # ---- roles ----
    def register_role(self, role: Role) -> None:
        self._roles[role.role_id] = role

    def get_role(self, role_id: str) -> Role | None:
        return self._roles.get(role_id)

    @property
    def roles(self) -> dict[str, Role]:
        return dict(self._roles)

    # ---- permissions ----
    def register_permission(self, permission: Permission) -> None:
        self._permissions[permission.permission_id] = permission

    def get_permission(self, permission_id: str) -> Permission | None:
        return self._permissions.get(permission_id)

    @property
    def permissions(self) -> dict[str, Permission]:
        return dict(self._permissions)

    # ---- policies ----
    def register_policy(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    def get_policy(self, policy_id: str) -> Policy | None:
        return self._policies.get(policy_id)

    @property
    def policies(self) -> dict[str, Policy]:
        return dict(self._policies)

    def policies_for(self, resource: str, action: str) -> tuple[Policy, ...]:
        """Enabled policies matching resource+action, highest priority first."""
        matched = [
            policy
            for policy in self._policies.values()
            if policy.enabled
            and policy.resource == resource
            and policy.action == action
        ]
        return tuple(sorted(matched, key=lambda policy: (policy.priority, policy.policy_id)))

    # ---- role permission mapping ----
    def assign_permission_to_role(self, role_id: str, permission_id: str) -> None:
        self._role_permissions.setdefault(role_id, set()).add(permission_id)

    def permissions_for_role(self, role_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._role_permissions.get(role_id, ())))

    def role_permissions(self) -> dict[str, tuple[str, ...]]:
        return {
            role_id: tuple(sorted(permission_ids))
            for role_id, permission_ids in self._role_permissions.items()
        }


def register_standard_governance(registry: GovernanceRegistry) -> None:
    """Register standard roles, permissions, policies and role mappings."""
    for role in build_standard_roles():
        registry.register_role(role)
    for permission in build_standard_permissions():
        registry.register_permission(permission)
    for policy in build_standard_policies():
        registry.register_policy(policy)
    for role_id, permission_ids in STANDARD_ROLE_PERMISSIONS.items():
        for permission_id in permission_ids:
            registry.assign_permission_to_role(role_id, permission_id)


def build_standard_governance() -> GovernanceRegistry:
    """Build a fully populated registry with the standard governance baseline."""
    registry = GovernanceRegistry()
    register_standard_governance(registry)
    return registry
