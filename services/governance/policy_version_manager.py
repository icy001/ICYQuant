"""
Policy Version Manager — manages version lifecycle and history for policy families.

The version manager is the authority on:
  - Creating new versions from existing ones
  - Bumping version numbers (major/minor/patch)
  - Tracking version lineage and history
  - Comparing versions (diffs)
  - Rolling back to previous versions
  - Archiving old versions
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .policy_version import PolicyVersion
from .policy_registry import PolicyRegistry
from .policy_repository import PolicyRepository
from .policy_status import PolicyLifecycleStatus, VersionStatus


# ---------------------------------------------------------------------------
# Version diff
# ---------------------------------------------------------------------------

@dataclass
class VersionDiff:
    """Diff between two policy versions."""

    policy_id: str = ""
    from_version: str = ""
    to_version: str = ""

    # Changes
    name_changed: bool = False
    description_changed: bool = False
    scope_changed: bool = False
    priority_changed: bool = False

    # Rule changes
    rules_added: List[str] = field(default_factory=list)
    rules_removed: List[str] = field(default_factory=list)
    rules_modified: List[str] = field(default_factory=list)
    rules_unchanged: int = 0

    # Metadata changes
    metadata_changes: List[str] = field(default_factory=list)

    # Content hash
    hash_changed: bool = False

    # Status
    status_change: Tuple[str, str] = ("", "")

    @property
    def has_changes(self) -> bool:
        return (
            self.name_changed
            or self.description_changed
            or self.scope_changed
            or self.priority_changed
            or bool(self.rules_added)
            or bool(self.rules_removed)
            or bool(self.rules_modified)
            or self.hash_changed
        )

    @property
    def change_summary(self) -> str:
        parts = []
        if self.name_changed:
            parts.append("name changed")
        if self.scope_changed:
            parts.append(f"scope: {self.status_change[0]}→{self.status_change[1]}")
        if self.rules_added:
            parts.append(f"+{len(self.rules_added)} rules")
        if self.rules_removed:
            parts.append(f"-{len(self.rules_removed)} rules")
        if self.rules_modified:
            parts.append(f"~{len(self.rules_modified)} rules")
        if not parts:
            parts.append("no changes")
        return "; ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "name_changed": self.name_changed,
            "description_changed": self.description_changed,
            "scope_changed": self.scope_changed,
            "priority_changed": self.priority_changed,
            "rules_added": self.rules_added,
            "rules_removed": self.rules_removed,
            "rules_modified": self.rules_modified,
            "rules_unchanged": self.rules_unchanged,
            "hash_changed": self.hash_changed,
            "has_changes": self.has_changes,
            "change_summary": self.change_summary,
        }


# ---------------------------------------------------------------------------
# Version Manager
# ---------------------------------------------------------------------------

@dataclass
class PolicyVersionManager:
    """
    Manages policy version lifecycle and history.

    Core responsibilities:
      - Create new draft versions (major/minor/patch bumps)
      - Compare versions (diff)
      - Rollback to previous versions
      - Archive and prune old versions
      - Track version lineage
    """

    registry: Optional[PolicyRegistry] = None
    repository: Optional[PolicyRepository] = None

    # ------------------------------------------------------------------
    # Version creation
    # ------------------------------------------------------------------

    def create_next_version(
        self,
        policy_id: str,
        bump: str = "minor",
        created_by: str = "SYSTEM",
        changes: str = "",
        from_version_id: str = "",
    ) -> PolicyVersion:
        """
        Create a new draft version from an existing one.

        Args:
            policy_id: The policy family to create a new version for.
            bump: "major", "minor", or "patch".
            created_by: Actor creating the version.
            changes: Description of changes.
            from_version_id: Base version (defaults to active version).
        """
        source = self._get_source_version(policy_id, from_version_id)
        if source is None:
            raise ValueError(
                f"No version found for policy '{policy_id}'"
            )

        new_version = source.create_next_draft(
            version_bump=bump, created_by=created_by
        )

        if changes:
            new_version.metadata.change_summary = changes
            new_version.description = f"{source.description}\n\nChanges in v{new_version.version}: {changes}"

        # Persist
        if self.registry:
            self.registry.register(new_version)
        if self.repository:
            self.repository.save(new_version, created_by)

        return new_version

    def create_draft_from_snapshot(
        self,
        policy_id: str,
        snapshot: Dict[str, Any],
        created_by: str = "SYSTEM",
    ) -> PolicyVersion:
        """Create a new draft from a saved snapshot."""
        base = self._get_source_version(policy_id)
        if base is None:
            raise ValueError(f"No version found for policy '{policy_id}'")

        draft = PolicyVersion(
            policy_id=policy_id,
            version=self._bump_minor(base.version),
            name=snapshot.get("name", base.name),
            description=snapshot.get("description", base.description),
            scope=snapshot.get("scope", base.scope),
            parent_version=base.version_id,
            created_by=created_by,
        )

        for rd in snapshot.get("rules", []):
            from .policy_rule import PolicyRule
            draft.add_rule(PolicyRule.from_dict(rd))

        if self.registry:
            self.registry.register(draft)
        if self.repository:
            self.repository.save(draft, created_by)

        return draft

    # ------------------------------------------------------------------
    # Version comparison
    # ------------------------------------------------------------------

    def diff(
        self,
        policy_id: str,
        version_a: str,
        version_b: str = "",
    ) -> VersionDiff:
        """
        Compare two versions of a policy.

        If version_b is empty, compares against the active version.
        """
        va = self._get_source_version(policy_id, version_a)
        vb = self._get_source_version(policy_id, version_b) if version_b else (
            self.registry.get_active(policy_id) if self.registry else None
        )

        if va is None or vb is None:
            raise ValueError("Both versions must exist for comparison")

        diff = VersionDiff(
            policy_id=policy_id,
            from_version=va.version,
            to_version=vb.version,
            name_changed=va.name != vb.name,
            description_changed=va.description != vb.description,
            scope_changed=va.scope != vb.scope,
            priority_changed=va.priority != vb.priority,
            hash_changed=va.content_hash != vb.content_hash,
        )

        # Compare rules
        a_rules = {r.rule_id: r.to_dict() for r in va.rules}
        b_rules = {r.rule_id: r.to_dict() for r in vb.rules}

        a_ids = set(a_rules.keys())
        b_ids = set(b_rules.keys())

        diff.rules_added = sorted(b_ids - a_ids)
        diff.rules_removed = sorted(a_ids - b_ids)

        for rid in a_ids & b_ids:
            if a_rules[rid] != b_rules[rid]:
                diff.rules_modified.append(rid)

        diff.rules_unchanged = len(a_ids & b_ids) - len(diff.rules_modified)

        return diff

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(
        self,
        policy_id: str,
        target_version_id: str,
        actor: str = "SYSTEM",
    ) -> PolicyVersion:
        """
        Rollback to a previous version.

        Creates a new version that is a copy of the target version,
        with a patch bump.
        """
        target = self._get_source_version(policy_id, target_version_id)
        if target is None:
            raise ValueError(f"Target version not found: {target_version_id}")

        rollback_version = target.create_next_draft(
            version_bump="patch", created_by=actor
        )
        rollback_version.metadata.change_summary = (
            f"Rollback to v{target.version}"
        )
        rollback_version.metadata.breaking_change = True

        if self.registry:
            self.registry.register(rollback_version)
        if self.repository:
            self.repository.save(rollback_version, actor)

        return rollback_version

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_version_history(
        self, policy_id: str
    ) -> List[Dict[str, Any]]:
        """Get the full version history for a policy family."""
        if self.registry:
            versions = self.registry.get_version_history(policy_id)
        elif self.repository:
            versions = self.repository.load_all(policy_id)
        else:
            return []

        return sorted(
            [
                {
                    "version_id": v.version_id,
                    "version": v.version,
                    "status": v.status.name,
                    "created_at": v.created_at,
                    "created_by": v.created_by,
                    "activated_at": v.activated_at,
                    "change_summary": v.metadata.change_summary,
                    "content_hash": v.content_hash,
                    "parent_version": v.parent_version,
                    "superseded_by": v.superseded_by,
                }
                for v in versions
            ],
            key=lambda x: x["created_at"],
            reverse=True,
        )

    def get_version_lineage(self, policy_id: str) -> List[Dict[str, str]]:
        """Get the version lineage (parent chain)."""
        versions = {}
        if self.registry:
            for v in self.registry.get_all_versions(policy_id):
                versions[v.version_id] = v

        lineage: List[Dict[str, str]] = []
        # Start from latest and trace back
        current = max(
            versions.values(), key=lambda v: v.created_at
        ) if versions else None

        while current:
            lineage.append({
                "version_id": current.version_id,
                "version": current.version,
                "status": current.status.name,
            })
            if current.parent_version and current.parent_version in versions:
                current = versions[current.parent_version]
            else:
                break

        return lineage

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    def archive_old_versions(
        self,
        policy_id: str,
        keep_count: int = 5,
        actor: str = "SYSTEM",
    ) -> int:
        """
        Archive old, superseded versions, keeping the N most recent.

        Returns the number of versions archived.
        """
        if self.registry:
            versions = sorted(
                self.registry.get_all_versions(policy_id),
                key=lambda v: v.created_at,
                reverse=True,
            )
        elif self.repository:
            versions = sorted(
                self.repository.load_all(policy_id),
                key=lambda v: v.created_at,
                reverse=True,
            )
        else:
            return 0

        archived = 0
        for version in versions[keep_count:]:
            if version.status in (
                PolicyLifecycleStatus.SUPERSEDED,
                PolicyLifecycleStatus.EXPIRED,
            ):
                version.archive(actor)
                if self.repository:
                    self.repository.save(version, actor)
                archived += 1

        return archived

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_source_version(
        self, policy_id: str, version_id: str = ""
    ) -> Optional[PolicyVersion]:
        """Get the source version for a new version."""
        if version_id and self.registry:
            return self.registry.get(policy_id, version_id)
        if self.registry:
            return self.registry.get(policy_id)  # Active or latest
        if self.repository:
            if version_id:
                return self.repository.load(policy_id, version_id)
            return self.repository.load(policy_id)
        return None

    @staticmethod
    def _bump_minor(version: str) -> str:
        parts = version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{major}.{minor + 1}.0"

    def __repr__(self) -> str:
        return "PolicyVersionManager()"
