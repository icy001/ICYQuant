"""Tool Permission Manager — RBAC-based access control for tool execution.

Pipeline:
    Agent Role -> Permission Set -> Tool Access Check
        -> Grant / Deny
        -> Audit Log

Supports RBAC with scope, resource-level policies, and
read/write/execute permission levels.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Enums ──

class PermissionLevel(str, Enum):
    """Permission access level."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class AccessDecision(str, Enum):
    """Result of an access check."""

    ALLOW = "allow"
    DENY = "deny"
    NOT_APPLICABLE = "not_applicable"


# ── Permission ──

@dataclass
class Permission:
    """A single permission definition."""

    name: str  # e.g., "research.execute", "order.create"
    description: str = ""
    level: PermissionLevel = PermissionLevel.EXECUTE
    resource_type: str = ""  # e.g., "backtest", "order", "strategy"
    scope: str = "*"  # e.g., "*", "project:123", "strategy:456"

    # ── Helpers ──

    def matches(self, required: str) -> bool:
        """Check if this permission satisfies a required permission.

        Supports wildcard matching: "research.*" matches "research.execute".

        Args:
            required: The required permission string.

        Returns:
            True if this permission grants the required access.
        """
        if self.name == required:
            return True
        if self.name.endswith(".*"):
            prefix = self.name[:-2]
            return required.startswith(prefix)
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "level": self.level.value,
            "resource_type": self.resource_type,
            "scope": self.scope,
        }


# ── Role ──

@dataclass
class Role:
    """A role with associated permissions."""

    name: str
    description: str = ""
    permissions: Set[str] = field(default_factory=set)
    inherits_from: List[str] = field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        """Check if this role grants a specific permission.

        Args:
            permission: The permission to check.

        Returns:
            True if the role has the permission.
        """
        for p in self.permissions:
            if p == permission or (p.endswith(".*") and permission.startswith(p[:-2])):
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "permissions": list(self.permissions),
            "inherits_from": self.inherits_from,
        }


# ── PolicyRule ──

@dataclass
class PolicyRule:
    """A single policy rule for access control."""

    rule_id: str = ""
    description: str = ""
    effect: AccessDecision = AccessDecision.ALLOW
    principals: List[str] = field(default_factory=list)  # agent IDs or "*"
    actions: List[str] = field(default_factory=list)  # tool names or "*"
    resources: List[str] = field(default_factory=list)  # resource identifiers
    conditions: Dict[str, Any] = field(default_factory=dict)  # e.g., {"time_of_day": "trading_hours"}
    priority: int = 0  # Higher priority rules evaluated first


# ── ToolPermissionManager ──

class ToolPermissionManager:
    """RBAC-based permission manager for tool access control.

    Manages roles, permissions, and policy rules. Evaluates whether
    an agent has the required permissions to execute a specific tool.

    Supports:
        - Role-based access control (RBAC)
        - Permission wildcard matching
        - Role inheritance
        - Policy rule evaluation with priority
        - Resource-level scoping
        - Deny-by-default

    Usage:
        pm = ToolPermissionManager()
        pm.register_role(Role(name="researcher", permissions={"research.execute"}))
        pm.assign_role("agent-001", "researcher")
        decision = pm.check_access("agent-001", "backtest.run")
    """

    def __init__(self) -> None:
        """Initialize the permission manager."""
        self._roles: Dict[str, Role] = {}
        self._agent_roles: Dict[str, List[str]] = {}  # agent_id -> [role_name, ...]
        self._policies: List[PolicyRule] = []

        # ── Default Roles ──
        self._register_default_roles()

        self._initialized: bool = False
        logger.info("ToolPermissionManager created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the permission manager."""
        self._initialized = True
        logger.info("ToolPermissionManager initialized")

    async def shutdown(self) -> None:
        """Shutdown the permission manager."""
        self._roles.clear()
        self._agent_roles.clear()
        self._policies.clear()
        self._initialized = False
        logger.info("ToolPermissionManager shutdown complete")

    # ── Role Management ──

    def register_role(self, role: Role) -> None:
        """Register a role.

        Args:
            role: The role to register.
        """
        self._roles[role.name] = role
        logger.info(f"Role registered: {role.name} ({len(role.permissions)} permissions)")

    def get_role(self, role_name: str) -> Optional[Role]:
        """Get a role by name.

        Args:
            role_name: The role name.

        Returns:
            The Role, or None if not found.
        """
        return self._roles.get(role_name)

    def assign_role(self, agent_id: str, role_name: str) -> None:
        """Assign a role to an agent.

        Args:
            agent_id: The agent identifier.
            role_name: The role to assign.

        Raises:
            KeyError: If the role does not exist.
        """
        if role_name not in self._roles:
            raise KeyError(f"Role not found: {role_name}")
        if agent_id not in self._agent_roles:
            self._agent_roles[agent_id] = []
        if role_name not in self._agent_roles[agent_id]:
            self._agent_roles[agent_id].append(role_name)
        logger.info(f"Role '{role_name}' assigned to agent '{agent_id}'")

    def revoke_role(self, agent_id: str, role_name: str) -> None:
        """Revoke a role from an agent.

        Args:
            agent_id: The agent identifier.
            role_name: The role to revoke.
        """
        if agent_id in self._agent_roles and role_name in self._agent_roles[agent_id]:
            self._agent_roles[agent_id].remove(role_name)
            logger.info(f"Role '{role_name}' revoked from agent '{agent_id}'")

    def get_agent_roles(self, agent_id: str) -> List[str]:
        """Get the roles assigned to an agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            List of role names.
        """
        return self._agent_roles.get(agent_id, [])

    # ── Permission Resolution ──

    def get_effective_permissions(self, agent_id: str) -> Set[str]:
        """Get the full set of effective permissions for an agent.

        Resolves role inheritance and aggregates all permissions.

        Args:
            agent_id: The agent identifier.

        Returns:
            Set of permission strings.
        """
        role_names = self.get_agent_roles(agent_id)
        permissions: Set[str] = set()

        visited: Set[str] = set()

        def resolve(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            role = self._roles.get(name)
            if role is None:
                return
            permissions.update(role.permissions)
            for parent in role.inherits_from:
                resolve(parent)

        for role_name in role_names:
            resolve(role_name)

        return permissions

    def check_permission(self, agent_id: str, permission: str) -> bool:
        """Check if an agent has a specific permission.

        Args:
            agent_id: The agent identifier.
            permission: The permission string to check.

        Returns:
            True if the agent has the permission.
        """
        effective = self.get_effective_permissions(agent_id)
        for p in effective:
            if p == permission or (p.endswith(".*") and permission.startswith(p[:-2])):
                return True
        return False

    # ── Access Check ──

    def check_access(
        self,
        agent_id: str,
        tool_name: str,
        resource: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """Check whether an agent can access a tool.

        Evaluates policies in priority order. First matching policy
        determines the decision.

        Args:
            agent_id: The agent identifier.
            tool_name: The tool to check access for.
            resource: Optional resource identifier for scoping.
            context: Optional context for condition evaluation.

        Returns:
            AccessDecision.ALLOW or AccessDecision.DENY.
        """
        # Sort policies by priority (descending)
        sorted_policies = sorted(self._policies, key=lambda p: -p.priority)

        for policy in sorted_policies:
            if self._policy_applies(policy, agent_id, tool_name, resource, context):
                logger.debug(
                    f"Policy match: {policy.rule_id} -> {policy.effect.value} "
                    f"for agent={agent_id}, tool={tool_name}"
                )
                return policy.effect

        # Deny by default
        logger.debug(f"No matching policy: deny access for {agent_id} to {tool_name}")
        return AccessDecision.DENY

    def add_policy(self, policy: PolicyRule) -> None:
        """Add a policy rule.

        Args:
            policy: The PolicyRule to add.
        """
        self._policies.append(policy)
        logger.info(f"Policy added: {policy.rule_id} (effect={policy.effect.value})")

    # ── Private Methods ──

    def _register_default_roles(self) -> None:
        """Register the default role hierarchy."""
        defaults: Dict[str, Dict[str, Any]] = {
            "admin": {
                "description": "Full platform access",
                "permissions": {"*.*"},
                "inherits": [],
            },
            "researcher": {
                "description": "Research and analysis access",
                "permissions": {"research.*", "market_data.read", "scheduler.execute"},
                "inherits": [],
            },
            "analyst": {
                "description": "Market analysis access",
                "permissions": {"market_data.*", "strategy.read", "portfolio.read"},
                "inherits": [],
            },
            "trader": {
                "description": "Trading execution access",
                "permissions": {"order.*", "portfolio.read", "risk.read", "strategy.execute"},
                "inherits": [],
            },
            "viewer": {
                "description": "Read-only access",
                "permissions": {"market_data.read", "portfolio.read", "research.read"},
                "inherits": [],
            },
            "orchestrator": {
                "description": "Workflow orchestration access",
                "permissions": {"workflow.*", "scheduler.*", "research.execute"},
                "inherits": [],
            },
        }
        for name, config in defaults.items():
            self.register_role(Role(
                name=name,
                description=config["description"],
                permissions=config["permissions"],
                inherits_from=config["inherits"],
            ))

    def _policy_applies(
        self,
        policy: PolicyRule,
        agent_id: str,
        tool_name: str,
        resource: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> bool:
        """Check if a policy rule applies to the current access request.

        Args:
            policy: The policy rule.
            agent_id: The agent identifier.
            tool_name: The tool name.
            resource: Optional resource identifier.
            context: Optional evaluation context.

        Returns:
            True if the policy applies.
        """
        # Check principals
        if policy.principals and "*" not in policy.principals:
            if agent_id not in policy.principals:
                return False

        # Check actions (tool names)
        if policy.actions and "*" not in policy.actions:
            if tool_name not in policy.actions:
                # Check wildcard
                matched = False
                for action in policy.actions:
                    if action.endswith(".*") and tool_name.startswith(action[:-2]):
                        matched = True
                        break
                if not matched:
                    return False

        # Check resources
        if policy.resources and resource:
            if resource not in policy.resources and "*" not in policy.resources:
                return False

        # Check conditions (simplified)
        if policy.conditions and context:
            for key, value in policy.conditions.items():
                if context.get(key) != value:
                    return False

        return True

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get permission manager status."""
        return {
            "roles": len(self._roles),
            "role_names": list(self._roles.keys()),
            "agents_with_roles": len(self._agent_roles),
            "policies": len(self._policies),
            "initialized": self._initialized,
        }
