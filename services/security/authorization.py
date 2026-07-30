"""
ICYQuant Authorization Service

RBAC + ABAC authorization with policy enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    APPROVE = "approve"
    REJECT = "reject"
    DEPLOY = "deploy"
    AUDIT = "audit"


class ResourceType(str, Enum):
    TRADE = "trade"
    ORDER = "order"
    POSITION = "position"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    MODEL = "model"
    AI_AGENT = "ai_agent"
    POLICY = "policy"
    USER = "user"
    SYSTEM = "system"
    AUDIT_LOG = "audit_log"
    SECRET = "secret"


@dataclass
class PermissionGrant:
    resource: ResourceType
    permissions: Set[Permission]
    condition: Optional[str] = None

    def can_perform(self, resource: ResourceType, permission: Permission, context: Optional[Dict] = None) -> bool:
        if self.resource != resource:
            return False
        if permission not in self.permissions:
            return False
        if self.condition and context:
            return self._evaluate_condition(self.condition, context)
        return True

    def to_dict(self) -> Dict:
        return {
            "resource": self.resource.value,
            "permissions": [p.value for p in self.permissions],
            "condition": self.condition,
        }

    @staticmethod
    def _evaluate_condition(condition: str, context: Dict) -> bool:
        try:
            return bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            return False


@dataclass
class Role:
    id: str
    name: str
    description: str = ""
    grants: List[PermissionGrant] = field(default_factory=list)
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def has_permission(self, resource: ResourceType, permission: Permission, context: Optional[Dict] = None) -> bool:
        for grant in self.grants:
            if grant.can_perform(resource, permission, context):
                return True
        return False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "grants": [g.to_dict() for g in self.grants],
            "isSystem": self.is_system,
        }


@dataclass
class ABACPolicy:
    id: str
    name: str
    description: str
    attribute: str
    operator: str
    value: Any
    effect: str = "allow"
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def evaluate(self, attributes: Dict) -> bool:
        attr_val = attributes.get(self.attribute)
        if attr_val is None:
            return False
        operators = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "ge": lambda a, b: a >= b,
            "le": lambda a, b: a <= b,
            "in": lambda a, b: a in b if isinstance(b, (list, set)) else False,
            "contains": lambda a, b: b in str(a) if a else False,
        }
        op_fn = operators.get(self.operator)
        if not op_fn:
            return False
        return op_fn(attr_val, self.value)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "attribute": self.attribute,
            "operator": self.operator,
            "value": self.value,
            "effect": self.effect,
            "priority": self.priority,
            "enabled": self.enabled,
        }


class AuthorizationError(Exception):
    pass


class AuthorizationService:
    """
    RBAC + ABAC authorization service.

    Supports role-based access control with attribute-based conditions.
    """

    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[str]] = {}
        self._abac_policies: List[ABACPolicy] = []
        self._assignments: Dict[str, List[str]] = {}

        self._init_default_roles()

    def _init_default_roles(self):
        admin = Role(
            id="admin",
            name="System Administrator",
            description="Full system access",
            is_system=True,
            grants=[
                PermissionGrant(resource=ResourceType.SYSTEM, permissions={Permission.ADMIN}),
                PermissionGrant(resource=ResourceType.USER, permissions={Permission.READ, Permission.WRITE, Permission.ADMIN}),
                PermissionGrant(resource=ResourceType.POLICY, permissions={Permission.READ, Permission.WRITE, Permission.APPROVE}),
                PermissionGrant(resource=ResourceType.SECRET, permissions={Permission.READ, Permission.WRITE}),
                PermissionGrant(resource=ResourceType.AUDIT_LOG, permissions={Permission.READ, Permission.ADMIN}),
            ],
        )
        trader = Role(
            id="trader",
            name="Trader",
            description="Trading operations",
            grants=[
                PermissionGrant(resource=ResourceType.TRADE, permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE}),
                PermissionGrant(resource=ResourceType.ORDER, permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE}),
                PermissionGrant(resource=ResourceType.POSITION, permissions={Permission.READ}),
            ],
        )
        risk_manager = Role(
            id="risk_manager",
            name="Risk Manager",
            description="Risk oversight",
            grants=[
                PermissionGrant(resource=ResourceType.RISK, permissions={Permission.READ, Permission.WRITE, Permission.APPROVE}),
                PermissionGrant(resource=ResourceType.PORTFOLIO, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.TRADE, permissions={Permission.READ}),
            ],
        )
        researcher = Role(
            id="researcher",
            name="Researcher",
            description="Research and strategy development",
            grants=[
                PermissionGrant(resource=ResourceType.STRATEGY, permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE}),
                PermissionGrant(resource=ResourceType.MODEL, permissions={Permission.READ, Permission.WRITE}),
                PermissionGrant(resource=ResourceType.PORTFOLIO, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.RISK, permissions={Permission.READ}),
            ],
        )
        auditor = Role(
            id="auditor",
            name="Auditor",
            description="Audit and compliance review",
            grants=[
                PermissionGrant(resource=ResourceType.AUDIT_LOG, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.TRADE, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.ORDER, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.POSITION, permissions={Permission.READ}),
            ],
        )
        ops = Role(
            id="ops",
            name="Operations Engineer",
            description="Platform operations",
            grants=[
                PermissionGrant(resource=ResourceType.SYSTEM, permissions={Permission.READ, Permission.DEPLOY}),
                PermissionGrant(resource=ResourceType.POLICY, permissions={Permission.READ}),
                PermissionGrant(resource=ResourceType.SECRET, permissions={Permission.READ}),
            ],
        )

        for role in [admin, trader, risk_manager, researcher, auditor, ops]:
            self._roles[role.id] = role

    def create_role(self, role: Role) -> Role:
        if role.id in self._roles:
            raise AuthorizationError(f"Role {role.id} already exists")
        self._roles[role.id] = role
        logger.info(f"Role created: {role.name}")
        return role

    def delete_role(self, role_id: str):
        role = self._roles.get(role_id)
        if not role:
            raise AuthorizationError(f"Role {role_id} not found")
        if role.is_system:
            raise AuthorizationError("Cannot delete system role")
        del self._roles[role_id]

    def assign_role(self, user_id: str, role_id: str):
        if role_id not in self._roles:
            raise AuthorizationError(f"Role {role_id} not found")
        if user_id not in self._user_roles:
            self._user_roles[user_id] = []
        if role_id not in self._user_roles[user_id]:
            self._user_roles[user_id].append(role_id)

    def revoke_role(self, user_id: str, role_id: str):
        if user_id in self._user_roles and role_id in self._user_roles[user_id]:
            self._user_roles[user_id].remove(role_id)

    def check_permission(
        self,
        user_id: str,
        resource: ResourceType,
        permission: Permission,
        context: Optional[Dict] = None,
    ) -> bool:
        if user_id == "system":
            return True

        role_ids = self._user_roles.get(user_id, [])
        for role_id in role_ids:
            role = self._roles.get(role_id)
            if role and role.has_permission(resource, permission, context):
                return True

        for policy in self._abac_policies:
            if policy.enabled and policy.evaluate(context or {}):
                if policy.effect == "allow":
                    return True

        return False

    def create_abac_policy(self, policy: ABACPolicy) -> ABACPolicy:
        self._abac_policies.append(policy)
        self._abac_policies.sort(key=lambda p: p.priority, reverse=True)
        return policy

    def delete_abac_policy(self, policy_id: str):
        self._abac_policies = [p for p in self._abac_policies if p.id != policy_id]

    def get_user_permissions(self, user_id: str) -> List[Dict]:
        permissions = []
        role_ids = self._user_roles.get(user_id, [])
        for role_id in role_ids:
            role = self._roles.get(role_id)
            if role:
                for grant in role.grants:
                    for perm in grant.permissions:
                        permissions.append({
                            "role": role.name,
                            "resource": grant.resource.value,
                            "permission": perm.value,
                        })
        return permissions

    def list_roles(self) -> List[Role]:
        return list(self._roles.values())

    def get_role(self, role_id: str) -> Optional[Role]:
        return self._roles.get(role_id)

    def to_dict(self) -> Dict:
        return {
            "roles": [r.to_dict() for r in self._roles.values()],
            "userRoles": self._user_roles,
            "abacPolicies": [p.to_dict() for p in self._abac_policies],
        }
