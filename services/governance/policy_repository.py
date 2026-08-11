"""
Policy Repository — persistence layer for policy versions.

Abstracts storage of policy versions behind a clean interface.
Supports:
  - In-memory storage (default, for testing and simple deployments)
  - Pluggable backends (Redis, PostgreSQL, etc.)
  - Versioned storage with audit trail
  - Snapshot and rollback
  - Import/export of policy collections
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy_version import PolicyVersion
from .policy_status import PolicyLifecycleStatus
from .policy_exception import PolicyLoadException


# ---------------------------------------------------------------------------
# Abstract repository interface
# ---------------------------------------------------------------------------

class PolicyRepositoryBackend(ABC):
    """Abstract backend for policy version persistence."""

    @abstractmethod
    def save(self, version: PolicyVersion) -> None:
        """Persist a policy version."""

    @abstractmethod
    def load(self, policy_id: str, version_id: str) -> Optional[PolicyVersion]:
        """Load a specific policy version."""

    @abstractmethod
    def load_all(self, policy_id: str) -> List[PolicyVersion]:
        """Load all versions of a policy family."""

    @abstractmethod
    def delete(self, policy_id: str, version_id: str) -> bool:
        """Delete a specific policy version."""

    @abstractmethod
    def list_policy_ids(self) -> List[str]:
        """List all policy IDs."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored policies."""

    @abstractmethod
    def exists(self, policy_id: str, version_id: str) -> bool:
        """Check if a version exists in storage."""


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------

class InMemoryRepositoryBackend(PolicyRepositoryBackend):
    """
    Simple in-memory storage for policy versions.
    Suitable for testing, development, and single-process deployments.
    """

    def __init__(self):
        self._storage: Dict[str, Dict[str, PolicyVersion]] = {}

    def save(self, version: PolicyVersion) -> None:
        if version.policy_id not in self._storage:
            self._storage[version.policy_id] = {}
        self._storage[version.policy_id][version.version_id] = version

    def load(self, policy_id: str, version_id: str) -> Optional[PolicyVersion]:
        family = self._storage.get(policy_id)
        if not family:
            return None
        return family.get(version_id)

    def load_all(self, policy_id: str) -> List[PolicyVersion]:
        family = self._storage.get(policy_id, {})
        return list(family.values())

    def delete(self, policy_id: str, version_id: str) -> bool:
        family = self._storage.get(policy_id)
        if not family:
            return False
        if version_id not in family:
            return False
        del family[version_id]
        if not family:
            del self._storage[policy_id]
        return True

    def list_policy_ids(self) -> List[str]:
        return sorted(self._storage.keys())

    def clear(self) -> None:
        self._storage.clear()

    def exists(self, policy_id: str, version_id: str) -> bool:
        family = self._storage.get(policy_id, {})
        return version_id in family


# ---------------------------------------------------------------------------
# Repository (frontend with audit + snapshot support)
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single audit record for a repository operation."""
    operation: str  # SAVE, LOAD, DELETE, SNAPSHOT, RESTORE, CLEAR
    policy_id: str
    version_id: str
    actor: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyRepository:
    """
    Repository frontend for policy version persistence.

    Wraps a backend with:
      - Audit trail of all operations
      - Snapshot / rollback support
      - Load with content integrity verification
      - Error handling with domain exceptions
    """

    backend: PolicyRepositoryBackend = field(
        default_factory=InMemoryRepositoryBackend
    )

    # Audit trail
    audit_log: List[AuditEntry] = field(default_factory=list)
    audit_enabled: bool = True

    # Snapshots
    snapshots: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, version: PolicyVersion, actor: str = "SYSTEM") -> None:
        """Persist a policy version with audit."""
        self.backend.save(version)
        self._audit("SAVE", version.policy_id, version.version_id, actor)

    def load(
        self, policy_id: str, version_id: str = "", actor: str = "SYSTEM",
        verify_checksum: bool = True,
    ) -> Optional[PolicyVersion]:
        """
        Load a policy version.

        If version_id is empty, loads the latest version.
        If verify_checksum is True, verifies content integrity.
        """
        version = self.backend.load(policy_id, version_id)
        if version is None:
            # Try loading latest
            all_versions = self.backend.load_all(policy_id)
            if all_versions:
                version = max(all_versions, key=lambda v: v.created_at)

        if version is None:
            return None

        # Verify content integrity
        if verify_checksum and version.is_published:
            if not version.verify_checksum():
                raise PolicyLoadException(
                    policy_id=policy_id,
                    version_id=version.version_id,
                    storage_error="Checksum verification failed",
                )

        self._audit("LOAD", policy_id, version.version_id, actor)
        return version

    def load_all(
        self, policy_id: str, actor: str = "SYSTEM"
    ) -> List[PolicyVersion]:
        """Load all versions of a policy family."""
        versions = self.backend.load_all(policy_id)
        self._audit("LOAD_ALL", policy_id, "", actor)
        return versions

    def delete(
        self, policy_id: str, version_id: str, actor: str = "SYSTEM"
    ) -> bool:
        """Delete a specific version."""
        deleted = self.backend.delete(policy_id, version_id)
        self._audit(
            "DELETE", policy_id, version_id, actor,
            metadata={"success": deleted},
        )
        return deleted

    def exists(self, policy_id: str, version_id: str) -> bool:
        return self.backend.exists(policy_id, version_id)

    def list_policy_ids(self) -> List[str]:
        return self.backend.list_policy_ids()

    def clear(self, actor: str = "SYSTEM") -> None:
        """Clear all policies from storage."""
        self.backend.clear()
        self._audit("CLEAR", "*", "*", actor)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def save_all(
        self, versions: List[PolicyVersion], actor: str = "SYSTEM"
    ) -> int:
        """Persist multiple versions."""
        count = 0
        for v in versions:
            self.save(v, actor)
            count += 1
        return count

    def load_active(
        self, policy_ids: Optional[List[str]] = None
    ) -> List[PolicyVersion]:
        """Load all active versions (optionally filtered by policy_ids)."""
        ids = policy_ids or self.backend.list_policy_ids()
        active = []
        for pid in ids:
            for v in self.backend.load_all(pid):
                if v.status == PolicyLifecycleStatus.ACTIVE:
                    active.append(v)
        return active

    def export_all(self) -> List[Dict[str, Any]]:
        """Export all versions as dicts."""
        result = []
        for pid in self.backend.list_policy_ids():
            for v in self.backend.load_all(pid):
                result.append(v.to_dict())
        return result

    def import_all(
        self, data: List[Dict[str, Any]], actor: str = "SYSTEM"
    ) -> int:
        """Import versions from dicts."""
        count = 0
        for dd in data:
            self.save(PolicyVersion.from_dict(dd), actor)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Snapshot / Restore
    # ------------------------------------------------------------------

    def create_snapshot(
        self, name: str = "", actor: str = "SYSTEM"
    ) -> str:
        """
        Create a named snapshot of the entire repository.
        Returns the snapshot ID.
        """
        snapshot_id = name or f"SNAP-{int(time.time())}"
        self.snapshots[snapshot_id] = {
            "data": self.export_all(),
            "timestamp": time.time(),
            "actor": actor,
        }
        self._audit("SNAPSHOT", "*", snapshot_id, actor)
        return snapshot_id

    def restore_snapshot(
        self, snapshot_id: str, actor: str = "SYSTEM"
    ) -> int:
        """
        Restore the repository to a previous snapshot.
        Returns the number of versions restored.
        """
        snap = self.snapshots.get(snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot '{snapshot_id}' not found")

        self.backend.clear()
        count = self.import_all(snap["data"], actor)
        self._audit("RESTORE", "*", snapshot_id, actor)
        return count

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots."""
        return [
            {"snapshot_id": sid, "versions": len(s["data"]), "timestamp": s["timestamp"]}
            for sid, s in self.snapshots.items()
        ]

    def delete_snapshot(self, snapshot_id: str) -> bool:
        return self.snapshots.pop(snapshot_id, None) is not None

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _audit(
        self,
        operation: str,
        policy_id: str,
        version_id: str,
        actor: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.audit_enabled:
            return
        entry = AuditEntry(
            operation=operation,
            policy_id=policy_id,
            version_id=version_id,
            actor=actor,
            metadata=metadata or {},
        )
        self.audit_log.append(entry)

    def get_audit_trail(
        self, policy_id: str = "", limit: int = 100
    ) -> List[AuditEntry]:
        """Get audit trail, optionally filtered by policy_id."""
        if not policy_id:
            return self.audit_log[-limit:]
        return [
            e for e in self.audit_log
            if e.policy_id == policy_id
        ][-limit:]

    def clear_audit_trail(self) -> None:
        self.audit_log.clear()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "versions": self.export_all(),
            "snapshots": self.list_snapshots(),
            "audit_count": len(self.audit_log),
        }

    def __repr__(self) -> str:
        return (
            f"PolicyRepository(backend={type(self.backend).__name__}, "
            f"policies={len(self.backend.list_policy_ids())})"
        )
