"""
ICYQuant Data Access Control — enterprise RBAC/ABAC access control for data platform.

Provides role-based and attribute-based access control for datasets,
with user/role/dataset/permission management and audit integration.

Architecture:
    User → Role → Dataset → Permission → Audit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AccessLevel(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class ResourceType(str, Enum):
    DATASET = "dataset"
    STREAM = "stream"
    CATALOG = "catalog"
    SCHEMA = "schema"
    PIPELINE = "pipeline"
    API = "api"


@dataclass
class AccessPolicy:
    """An access control policy."""
    policy_id: str
    name: str
    resource_type: ResourceType
    resource_id: str
    principal_id: str
    principal_type: str  # user, role, group, service
    access_level: AccessLevel
    conditions: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DataAccessControl:
    """Enterprise access control for data platform resources.

    Supports:
        - RBAC: Role-based access control
        - ABAC: Attribute-based access control (via conditions)
        - Resource-level granularity (dataset/stream/catalog/schema/pipeline/api)
        - Policy expiration and audit
    """

    def __init__(self) -> None:
        self._policies: dict[str, AccessPolicy] = {}
        self._deny_count = 0
        self._allow_count = 0

    def grant(
        self,
        principal_id: str,
        principal_type: str,
        resource_type: ResourceType,
        resource_id: str,
        access_level: AccessLevel,
        conditions: Optional[dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> AccessPolicy:
        """Grant access to a resource."""
        import uuid

        policy = AccessPolicy(
            policy_id=str(uuid.uuid4()),
            name=f"{principal_type}:{principal_id}→{resource_type.value}:{resource_id}",
            resource_type=resource_type,
            resource_id=resource_id,
            principal_id=principal_id,
            principal_type=principal_type,
            access_level=access_level,
            conditions=conditions or {},
            expires_at=expires_at,
        )
        self._policies[policy.policy_id] = policy
        logger.info("Granted %s to %s:%s on %s:%s",
                     access_level.value, principal_type, principal_id,
                     resource_type.value, resource_id)
        return policy

    def revoke(self, policy_id: str) -> bool:
        """Revoke an access policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def check_access(
        self,
        principal_id: str,
        resource_type: ResourceType,
        resource_id: str,
        required_level: AccessLevel = AccessLevel.READ,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Check if a principal has sufficient access."""
        level_order = {
            AccessLevel.NONE: 0,
            AccessLevel.READ: 1,
            AccessLevel.WRITE: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.OWNER: 4,
        }
        required_rank = level_order[required_level]

        for policy in self._policies.values():
            if not policy.enabled:
                continue

            # Check expiration
            if policy.expires_at and policy.expires_at < datetime.now(timezone.utc):
                continue

            # Match principal
            if policy.principal_id != principal_id:
                continue

            # Match resource (wildcard * matches all)
            if policy.resource_id != "*" and policy.resource_id != resource_id:
                continue
            if policy.resource_type != resource_type:
                continue

            # Check conditions (ABAC)
            if policy.conditions and context:
                if not self._evaluate_conditions(policy.conditions, context):
                    continue

            # Check level
            if level_order[policy.access_level] >= required_rank:
                self._allow_count += 1
                return True

        self._deny_count += 1
        return False

    def list_policies_for_principal(self, principal_id: str) -> list[AccessPolicy]:
        """List all policies for a principal."""
        return [p for p in self._policies.values() if p.principal_id == principal_id]

    def list_policies_for_resource(self, resource_id: str) -> list[AccessPolicy]:
        """List all policies for a resource."""
        return [p for p in self._policies.values() if p.resource_id == resource_id]

    @staticmethod
    def _evaluate_conditions(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if actual != expected:
                return False
        return True

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def deny_count(self) -> int:
        return self._deny_count

    @property
    def allow_count(self) -> int:
        return self._allow_count
