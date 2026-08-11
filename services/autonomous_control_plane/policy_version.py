"""
Policy Version — Versioned policy management.

Supports policy version history, rollback, diff between versions,
and tracking of which version was active at any given time.
"""

from __future__ import annotations

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PolicyVersionRecord:
    """A single version of a policy."""
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    created_by: str = ""
    active: bool = False
    rule_content: Optional[dict] = None
    change_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "policy_id": self.policy_id,
            "version": self.version,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "active": self.active,
            "change_summary": self.change_summary,
        }


class PolicyVersion:
    """
    Manages version history for policies.

    Each policy can have multiple versions. Only one version of each
    policy is active at a time. Version history is preserved for audit.
    """

    def __init__(self):
        self._versions: dict[str, list[PolicyVersionRecord]] = {}
        self._active_version: dict[str, str] = {}  # policy_id → version_id

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    def create_version(
        self,
        policy_id: str,
        version: str,
        rule_content: Optional[dict] = None,
        created_by: str = "",
        change_summary: str = "",
    ) -> PolicyVersionRecord:
        """Create a new version of a policy."""
        record = PolicyVersionRecord(
            policy_id=policy_id,
            version=version,
            created_by=created_by,
            rule_content=rule_content,
            change_summary=change_summary,
        )

        self._versions.setdefault(policy_id, []).append(record)

        # Deactivate previous versions
        for v in self._versions[policy_id][:-1]:
            v.active = False

        record.active = True
        self._active_version[policy_id] = record.version_id

        logger.info("Policy %s version %s created", policy_id, version)
        return record

    def activate_version(self, policy_id: str, version: str) -> bool:
        """Activate a specific version of a policy."""
        versions = self._versions.get(policy_id, [])
        for v in versions:
            if v.version == version:
                # Deactivate all
                for all_v in versions:
                    all_v.active = False
                v.active = True
                self._active_version[policy_id] = v.version_id
                logger.info("Policy %s → v%s activated", policy_id, version)
                return True
        logger.warning("Policy %s version %s not found", policy_id, version)
        return False

    def get_active_version(self, policy_id: str) -> Optional[PolicyVersionRecord]:
        """Get the currently active version for a policy."""
        version_id = self._active_version.get(policy_id)
        if version_id:
            for versions in self._versions.get(policy_id, []):
                if versions.version_id == version_id:
                    return versions
        return None

    def get_history(self, policy_id: str) -> list[PolicyVersionRecord]:
        """Get the full version history for a policy."""
        return list(self._versions.get(policy_id, []))

    def diff(self, policy_id: str, version_a: str, version_b: str) -> dict:
        """Compute a simple diff between two policy versions."""
        versions = self._versions.get(policy_id, [])
        a_content = None
        b_content = None
        for v in versions:
            if v.version == version_a:
                a_content = v.rule_content
            if v.version == version_b:
                b_content = v.rule_content

        if a_content is None or b_content is None:
            return {"error": "version_not_found"}

        # Simple key diff
        changes = {}
        all_keys = set(a_content.keys()) | set(b_content.keys())
        for key in all_keys:
            old = a_content.get(key)
            new = b_content.get(key)
            if old != new:
                changes[key] = {"from": old, "to": new}

        return {
            "version_a": version_a,
            "version_b": version_b,
            "changes": changes,
            "change_count": len(changes),
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        total_versions = sum(len(v) for v in self._versions.values())
        return {
            "total_policies": len(self._versions),
            "total_versions": total_versions,
            "active_versions": len(self._active_version),
        }
