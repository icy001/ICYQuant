"""
Policy Registry — centralized registry for policy versions.

The registry is the single source of truth for which policy versions exist
and their current state. It provides:
  - Registration of new policy families and versions
  - Lookup by policy_id and version
  - Query for active versions
  - Version history per policy family
  - Scope-based filtering
  - Priority-ordered listing for evaluation
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .policy_version import PolicyVersion
from .policy_priority import PolicyPriorityLevel
from .policy_status import PolicyLifecycleStatus
from .policy_scope import PolicyScopeConstants, ScopeHierarchy


@dataclass
class PolicyRegistry:
    """
    Centralized registry of all policy versions.

    Organized as a two-level index:
      1. policy_id → {version_id → PolicyVersion}
      2. Active version index for fast evaluation lookups

    Supports:
      - Register, lookup, and query policy versions
      - Enforce single-active-version-per-policy
      - Scope-aware filtering
      - Priority-ordered evaluation listing
    """

    # Primary storage: policy_id → {version_id → PolicyVersion}
    _versions: Dict[str, Dict[str, PolicyVersion]] = field(default_factory=dict)

    # Active versions: policy_id → active version_id
    _active: Dict[str, str] = field(default_factory=dict)

    # Scope index: scope → {version_ids}
    _scope_index: Dict[str, Set[str]] = field(default_factory=dict)

    # Priority index: priority → {version_ids}
    _priority_index: Dict[PolicyPriorityLevel, Set[str]] = field(
        default_factory=dict
    )

    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, version: PolicyVersion) -> PolicyVersion:
        """
        Register a policy version in the registry.

        If this is the first version for a policy family, the policy_id
        acts as both the family identifier and the version identifier.
        """
        if not version.policy_id:
            raise ValueError("Policy version must have a policy_id")

        if version.policy_id not in self._versions:
            self._versions[version.policy_id] = {}

        self._versions[version.policy_id][version.version_id] = version

        # Update indexes
        self._index_scope(version)
        self._index_priority(version)

        # Track active versions
        if version.status == PolicyLifecycleStatus.ACTIVE:
            self._set_active(version.policy_id, version.version_id)

        self.updated_at = time.time()
        return version

    def unregister(self, policy_id: str, version_id: str) -> bool:
        """Remove a specific version from the registry."""
        if policy_id not in self._versions:
            return False
        version = self._versions[policy_id].pop(version_id, None)
        if version is None:
            return False

        # Clean up indexes
        self._deindex_scope(version)
        self._deindex_priority(version)

        # Clean active if needed
        if self._active.get(policy_id) == version_id:
            del self._active[policy_id]

        # Clean empty family
        if not self._versions[policy_id]:
            del self._versions[policy_id]

        self.updated_at = time.time()
        return True

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, policy_id: str, version_id: str = "") -> Optional[PolicyVersion]:
        """
        Get a specific policy version.

        If version_id is empty, returns the currently active version.
        """
        family = self._versions.get(policy_id)
        if not family:
            return None

        if version_id:
            return family.get(version_id)

        # Return active version
        active_id = self._active.get(policy_id)
        if active_id:
            return family.get(active_id)

        # No active version: return latest (by created_at)
        if family:
            return max(family.values(), key=lambda v: v.created_at)

        return None

    def get_active(self, policy_id: str) -> Optional[PolicyVersion]:
        """Get the currently active version of a policy."""
        active_id = self._active.get(policy_id)
        if not active_id:
            return None
        family = self._versions.get(policy_id, {})
        return family.get(active_id)

    def get_all_versions(self, policy_id: str) -> List[PolicyVersion]:
        """Get all versions of a policy family."""
        return list(self._versions.get(policy_id, {}).values())

    def get_version_history(self, policy_id: str) -> List[PolicyVersion]:
        """Get version history, sorted by creation time (newest first)."""
        versions = self.get_all_versions(policy_id)
        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    def exists(self, policy_id: str, version_id: str = "") -> bool:
        """Check if a policy version exists."""
        return self.get(policy_id, version_id) is not None

    @property
    def policy_count(self) -> int:
        """Number of distinct policy families."""
        return len(self._versions)

    @property
    def version_count(self) -> int:
        """Total number of registered versions."""
        return sum(len(v) for v in self._versions.values())

    @property
    def active_count(self) -> int:
        """Number of currently active policy versions."""
        return len(self._active)

    # ------------------------------------------------------------------
    # Activation management
    # ------------------------------------------------------------------

    def set_active(self, policy_id: str, version_id: str) -> bool:
        """
        Set the active version for a policy family.

        This deactivates the previously active version (if any) by
        transitioning it to SUPERSEDED.
        """
        family = self._versions.get(policy_id, {})
        version = family.get(version_id)
        if not version:
            return False

        # Deactivate current active
        old_active_id = self._active.get(policy_id)
        if old_active_id and old_active_id != version_id:
            old_version = family.get(old_active_id)
            if old_version and old_version.status == PolicyLifecycleStatus.ACTIVE:
                old_version.supersede(version_id)

        # Activate new version
        if version.status != PolicyLifecycleStatus.ACTIVE:
            version.activate()

        self._active[policy_id] = version_id
        self.updated_at = time.time()
        return True

    def deactivate(self, policy_id: str) -> bool:
        """Deactivate the active version of a policy."""
        active = self._active.pop(policy_id, None)
        if active:
            version = self.get(policy_id, active)
            if version and version.status == PolicyLifecycleStatus.ACTIVE:
                version.expire()
            self.updated_at = time.time()
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_active(self) -> List[PolicyVersion]:
        """List all currently active policy versions."""
        result = []
        for policy_id, version_id in self._active.items():
            version = self.get(policy_id, version_id)
            if version and version.status == PolicyLifecycleStatus.ACTIVE:
                result.append(version)
        return result

    def list_all(self) -> List[PolicyVersion]:
        """List all registered versions."""
        result = []
        for family in self._versions.values():
            result.extend(family.values())
        return result

    def list_policy_families(self) -> List[str]:
        """List all unique policy_ids."""
        return sorted(self._versions.keys())

    def list_by_scope(self, scope: str) -> List[PolicyVersion]:
        """List active policies matching a scope (including inheritance)."""
        result: List[PolicyVersion] = []
        # Match exact scope
        result.extend(
            v for v in self.list_active()
            if v.scope == scope
        )
        # Match ancestors (policies scoped to GLOBAL also apply)
        for v in self.list_active():
            if ScopeHierarchy.is_descendant(scope, v.scope):
                if v not in result:
                    result.append(v)
        return result

    def list_by_priority(self, priority: PolicyPriorityLevel) -> List[PolicyVersion]:
        """List active policies at a given priority level."""
        return [v for v in self.list_active() if v.priority == priority]

    def list_for_evaluation(
        self, scope: str = PolicyScopeConstants.GLOBAL
    ) -> List[PolicyVersion]:
        """
        List active versions applicable to a scope, sorted by evaluation order.

        Evaluation order:
          1. Higher priority first (EMERGENCY > CRITICAL > HIGH > NORMAL > LOW)
          2. Within same priority, most recently activated first
        """
        applicable = self.list_by_scope(scope)
        return sorted(
            applicable,
            key=lambda v: (
                -v.priority.value,  # Higher priority first
                -(v.activated_at or 0),  # Most recent first
            ),
        )

    def find_by_name(
        self, name: str, case_sensitive: bool = False
    ) -> List[PolicyVersion]:
        """Find policies by name (partial match)."""
        search = name if case_sensitive else name.lower()
        results = []
        for v in self.list_all():
            vname = v.name if case_sensitive else v.name.lower()
            if search in vname:
                results.append(v)
        return results

    def find_by_tag(self, tag: str) -> List[PolicyVersion]:
        """Find policies by metadata tag."""
        return [
            v for v in self.list_all()
            if tag in v.metadata.tags
        ]

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _index_scope(self, version: PolicyVersion) -> None:
        if version.scope not in self._scope_index:
            self._scope_index[version.scope] = set()
        self._scope_index[version.scope].add(version.version_id)

    def _deindex_scope(self, version: PolicyVersion) -> None:
        scope_set = self._scope_index.get(version.scope)
        if scope_set:
            scope_set.discard(version.version_id)

    def _index_priority(self, version: PolicyVersion) -> None:
        if version.priority not in self._priority_index:
            self._priority_index[version.priority] = set()
        self._priority_index[version.priority].add(version.version_id)

    def _deindex_priority(self, version: PolicyVersion) -> None:
        prio_set = self._priority_index.get(version.priority)
        if prio_set:
            prio_set.discard(version.version_id)

    def _set_active(self, policy_id: str, version_id: str) -> None:
        self._active[policy_id] = version_id

    def rebuild_indexes(self) -> None:
        """Rebuild all indexes from scratch."""
        self._scope_index.clear()
        self._priority_index.clear()
        for version in self.list_all():
            self._index_scope(version)
            self._index_priority(version)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def import_versions(self, versions: List[PolicyVersion]) -> int:
        """Import multiple versions at once."""
        count = 0
        for v in versions:
            self.register(v)
            count += 1
        return count

    def export_active(self) -> List[Dict[str, Any]]:
        """Export all active versions as dicts."""
        return [v.to_dict() for v in self.list_active()]

    def export_all(self) -> List[Dict[str, Any]]:
        """Export all versions as dicts."""
        return [v.to_dict() for v in self.list_all()]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "versions": self.export_all(),
            "active": dict(self._active),
            "policy_count": self.policy_count,
            "version_count": self.version_count,
            "active_count": self.active_count,
            "policy_ids": self.list_policy_families(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRegistry":
        registry = cls()
        registry._active = data.get("active", {})
        for vd in data.get("versions", []):
            registry.register(PolicyVersion.from_dict(vd))
        return registry

    def __repr__(self) -> str:
        return (
            f"PolicyRegistry(families={self.policy_count}, "
            f"versions={self.version_count}, active={self.active_count})"
        )

    def __contains__(self, policy_id: str) -> bool:
        return policy_id in self._versions

    def __len__(self) -> int:
        return self.version_count
