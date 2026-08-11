"""
Policy Version — versionable, auditable policy unit.

Each PolicyVersion is an immutable snapshot of a policy at a point in time.
Versions progress through a controlled lifecycle state machine:
  DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE → SUPERSEDED → ARCHIVED

Core principles:
  - Immutable after PUBLISHED — any change creates a new version.
  - Content hashing for integrity verification.
  - Full lifecycle tracking with timestamps per transition.
  - Explicit activation (no auto-activation on publish).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy_rule import PolicyRule
from .policy_metadata import PolicyMetadata
from .policy_priority import PolicyPriorityLevel
from .policy_status import (
    PolicyLifecycleStatus,
    PolicyStateMachine,
    VersionStatus,
)


# ---------------------------------------------------------------------------
# PolicyVersion
# ---------------------------------------------------------------------------

@dataclass
class PolicyVersion:
    """
    A single versioned snapshot of an institutional policy.

    Once activated, the version is immutable. Any modification creates a
    new version in DRAFT state. The version number follows semver: MAJOR.MINOR.PATCH.

    Attributes:
        version_id:   Unique identifier for this version.
        policy_id:    The policy family this version belongs to.
        version:      Semantic version string (e.g., "1.2.0").
        status:       Current lifecycle status.
        version_status: Simplified internal status.
        name:         Human-readable policy name.
        description:  Full policy description.
        scope:        Scope string (e.g., "GLOBAL", "PORTFOLIO").
        priority:     Evaluation priority level.
        enabled:      Whether this version is enabled for evaluation.
        rules:        The rule set for this version.
        metadata:     Structured metadata (owner, regulatory, review).
        parent_version: ID of the previous version this was derived from.
        superseded_by: ID of the version that supersedes this one.
        content_hash: SHA-256 hash of the policy content for integrity.
        checksum_verified: Whether the content hash was verified on load.
        custom:       Arbitrary custom data.

    Timing:
        created_at:       When this version record was created.
        updated_at:       Last modification time.
        validated_at:     When status moved to VALIDATED.
        approved_at:      When status moved to APPROVED.
        published_at:     When status moved to PUBLISHED.
        activated_at:     When status moved to ACTIVE.
        superseded_at:    When status moved to SUPERSEDED.
        archived_at:      When status moved to ARCHIVED.
        rejected_at:      When status moved to REJECTED.
        expired_at:       When status moved to EXPIRED.
    """

    # Identity
    version_id: str = field(
        default_factory=lambda: f"PV-{uuid.uuid4().hex[:12]}"
    )
    policy_id: str = ""  # The policy family this version belongs to

    # Versioning
    version: str = "0.1.0"
    status: PolicyLifecycleStatus = PolicyLifecycleStatus.DRAFT
    version_status: VersionStatus = VersionStatus.CURRENT

    # Content
    name: str = ""
    description: str = ""
    scope: str = "GLOBAL"
    priority: PolicyPriorityLevel = PolicyPriorityLevel.NORMAL
    enabled: bool = True
    rules: List[PolicyRule] = field(default_factory=list)
    metadata: PolicyMetadata = field(default_factory=PolicyMetadata)

    # Lineage
    parent_version: Optional[str] = None
    superseded_by: Optional[str] = None

    # Integrity
    content_hash: str = ""
    checksum_verified: bool = False

    # Custom extensibility
    custom: Dict[str, Any] = field(default_factory=dict)

    # ---- Timing ----
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "SYSTEM"

    validated_at: Optional[float] = None
    validated_by: Optional[str] = None

    approved_at: Optional[float] = None
    approved_by: Optional[str] = None

    published_at: Optional[float] = None
    published_by: Optional[str] = None

    activated_at: Optional[float] = None
    activated_by: Optional[str] = None

    superseded_at: Optional[float] = None
    superseded_by_actor: Optional[str] = None

    archived_at: Optional[float] = None
    archived_by: Optional[str] = None

    rejected_at: Optional[float] = None
    rejected_by: Optional[str] = None

    expired_at: Optional[float] = None

    # ---- Lifecycle methods ----

    def transition(
        self, to_status: PolicyLifecycleStatus, actor: str = "SYSTEM"
    ) -> None:
        """
        Attempt a lifecycle transition with validation.

        Raises ValueError if transition is invalid.
        Updates the corresponding timing field automatically.
        """
        PolicyStateMachine.validate_transition(self.status, to_status)

        old_status = self.status
        self.status = to_status
        self.updated_at = time.time()

        # Record timing for the transition
        _now = time.time()
        if to_status == PolicyLifecycleStatus.VALIDATED:
            self.validated_at = _now
            self.validated_by = actor
        elif to_status == PolicyLifecycleStatus.APPROVED:
            self.approved_at = _now
            self.approved_by = actor
        elif to_status == PolicyLifecycleStatus.PUBLISHED:
            self.published_at = _now
            self.published_by = actor
            # Published versions are immutable — freeze content hash
            self.content_hash = self.compute_content_hash()
        elif to_status == PolicyLifecycleStatus.ACTIVE:
            self.activated_at = _now
            self.activated_by = actor
        elif to_status == PolicyLifecycleStatus.SUPERSEDED:
            self.superseded_at = _now
        elif to_status == PolicyLifecycleStatus.ARCHIVED:
            self.archived_at = _now
            self.archived_by = actor
        elif to_status == PolicyLifecycleStatus.REJECTED:
            self.rejected_at = _now
            self.rejected_by = actor
        elif to_status == PolicyLifecycleStatus.EXPIRED:
            self.expired_at = _now

    def can_transition_to(self, to_status: PolicyLifecycleStatus) -> bool:
        """Check if a transition is valid without performing it."""
        return PolicyStateMachine.can_transition(self.status, to_status)

    @property
    def available_transitions(self) -> List[PolicyLifecycleStatus]:
        """Return list of valid next states."""
        return sorted(
            PolicyStateMachine.allowed_transitions(self.status),
            key=lambda s: s.name,
        )

    # ---- Validation helpers ----

    def validate(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Mark as VALIDATED."""
        self.transition(PolicyLifecycleStatus.VALIDATED, actor)
        return self

    def approve(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Mark as APPROVED."""
        self.transition(PolicyLifecycleStatus.APPROVED, actor)
        return self

    def reject(self, actor: str = "SYSTEM", reason: str = "") -> PolicyVersion:
        """Mark as REJECTED."""
        self.transition(PolicyLifecycleStatus.REJECTED, actor)
        if reason:
            self.metadata.add_review(actor, "rejected", reason)
        return self

    def publish(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Mark as PUBLISHED. Content hash is frozen at this point."""
        self.transition(PolicyLifecycleStatus.PUBLISHED, actor)
        return self

    def activate(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Mark as ACTIVE — this version is now in effect."""
        self.transition(PolicyLifecycleStatus.ACTIVE, actor)
        return self

    def supersede(self, superseded_by: str, actor: str = "SYSTEM") -> PolicyVersion:
        """Mark as SUPERSEDED by a newer version."""
        self.superseded_by = superseded_by
        self.superseded_by_actor = actor
        self.transition(PolicyLifecycleStatus.SUPERSEDED, actor)
        return self

    def revoke(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Revoke this published/active version."""
        if self.status not in (
            PolicyLifecycleStatus.PUBLISHED,
            PolicyLifecycleStatus.ACTIVE,
        ):
            raise ValueError(
                f"Cannot revoke from status {self.status.name}. "
                f"Must be PUBLISHED or ACTIVE."
            )
        self.transition(PolicyLifecycleStatus.REVOKED, actor)
        return self

    def expire(self) -> PolicyVersion:
        """Expire this active version."""
        self.transition(PolicyLifecycleStatus.EXPIRED)
        return self

    def archive(self, actor: str = "SYSTEM") -> PolicyVersion:
        """Archive this version."""
        self.transition(PolicyLifecycleStatus.ARCHIVED, actor)
        return self

    # ---- Derived logic ----


    @property
    def is_draft(self) -> bool:
        return self.status == PolicyLifecycleStatus.DRAFT

    @property
    def is_active(self) -> bool:
        return self.status == PolicyLifecycleStatus.ACTIVE

    @property
    def is_published(self) -> bool:
        return self.status in (
            PolicyLifecycleStatus.PUBLISHED,
            PolicyLifecycleStatus.ACTIVE,
            PolicyLifecycleStatus.SUPERSEDED,
        )

    @property
    def is_immutable(self) -> bool:
        """Once PUBLISHED, content must not change."""
        return self.status in (
            PolicyLifecycleStatus.PUBLISHED,
            PolicyLifecycleStatus.ACTIVE,
            PolicyLifecycleStatus.SUPERSEDED,
            PolicyLifecycleStatus.ARCHIVED,
            PolicyLifecycleStatus.EXPIRED,
        )

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def is_editable(self) -> bool:
        return self.status.is_editable

    @property
    def age_seconds(self) -> float:
        """Seconds since this version was created."""
        return time.time() - self.created_at

    @property
    def time_in_current_status(self) -> float:
        """Seconds spent in the current status."""
        timing_field = {
            PolicyLifecycleStatus.DRAFT: self.created_at,
            PolicyLifecycleStatus.VALIDATED: self.validated_at,
            PolicyLifecycleStatus.APPROVED: self.approved_at,
            PolicyLifecycleStatus.PUBLISHED: self.published_at,
            PolicyLifecycleStatus.ACTIVE: self.activated_at,
            PolicyLifecycleStatus.SUPERSEDED: self.superseded_at,
            PolicyLifecycleStatus.ARCHIVED: self.archived_at,
            PolicyLifecycleStatus.REJECTED: self.rejected_at,
            PolicyLifecycleStatus.REVOKED: self.archived_at,  # reuse timing if revoked→archived
            PolicyLifecycleStatus.EXPIRED: self.expired_at,
        }
        transition_time = timing_field.get(self.status)
        if transition_time is None:
            return 0.0
        return time.time() - transition_time

    # ---- Content hashing ----

    def compute_content_hash(self) -> str:
        """
        Compute a deterministic SHA-256 hash of policy content.

        Hashes: name, description, scope, rules (serialized).
        Does NOT include: version_id, policy_id, status, timing, metadata.
        """
        content = {
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "priority": self.priority.name,
            "enabled": self.enabled,
            "rules": [r.to_dict() for r in self.rules],
            "custom": self.custom,
        }
        # Deterministic JSON serialization
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_checksum(self) -> bool:
        """Verify that the content matches the stored hash."""
        if not self.content_hash:
            return True  # No hash to verify against
        current = self.compute_content_hash()
        self.checksum_verified = (current == self.content_hash)
        return self.checksum_verified

    def has_content_changed(self) -> bool:
        """Check if the content differs from the stored hash."""
        if not self.content_hash:
            return True  # No baseline
        return self.compute_content_hash() != self.content_hash

    # ---- Rule management ----

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule to this version."""
        self.rules.append(rule)
        self.updated_at = time.time()

    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule by ID."""
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        self.updated_at = time.time()

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        """Get a rule by ID."""
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    # ---- Cloning / Derivation ----

    def create_next_draft(
        self,
        version_bump: str = "minor",
        created_by: str = "SYSTEM",
    ) -> "PolicyVersion":
        """
        Create a new DRAFT version derived from this one.

        Args:
            version_bump: "major", "minor", or "patch".
            created_by: Actor creating the new version.
        """
        new_version_str = self._bump_version(version_bump)
        return PolicyVersion(
            policy_id=self.policy_id,
            version=new_version_str,
            name=self.name,
            description=self.description,
            scope=self.scope,
            priority=self.priority,
            enabled=self.enabled,
            rules=[PolicyRule.from_dict(r.to_dict()) for r in self.rules],
            metadata=PolicyMetadata.from_dict(self.metadata.to_dict()),
            parent_version=self.version_id,
            created_by=created_by,
            custom=dict(self.custom),
        )

    def snapshot(self) -> Dict[str, Any]:
        """
        Create a full serializable snapshot of this version.

        This snapshot is suitable for audit trails and rollback.
        """
        return self.to_dict()

    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> "PolicyVersion":
        """
        Restore version state from a previously created snapshot.
        Only allowed for DRAFT versions.
        """
        if self.status != PolicyLifecycleStatus.DRAFT:
            raise ValueError(
                f"Cannot restore snapshot — version is {self.status.name}, "
                f"must be DRAFT."
            )
        restored = PolicyVersion.from_dict(snapshot)
        # Preserve version identity and lineage
        restored.version_id = self.version_id
        restored.policy_id = self.policy_id
        restored.version = self.version
        restored.parent_version = self.parent_version
        restored.status = PolicyLifecycleStatus.DRAFT
        restored.created_at = self.created_at
        restored.created_by = self.created_by
        return restored

    # ---- Helpers ----

    @staticmethod
    def _bump_version(current: str, bump: str) -> str:
        """Bump a semver string."""
        parts = current.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if bump == "major":
            return f"{major + 1}.0.0"
        elif bump == "minor":
            return f"{major}.{minor + 1}.0"
        elif bump == "patch":
            return f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Unknown version bump: {bump}")

    @property
    def display_version(self) -> str:
        return f"v{self.version}"

    @property
    def full_identifier(self) -> str:
        """Combined policy_id + version for traceability."""
        return f"{self.policy_id}@{self.version}"

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            # Identity
            "version_id": self.version_id,
            "policy_id": self.policy_id,
            # Versioning
            "version": self.version,
            "status": self.status.name,
            "version_status": self.version_status.name,
            # Content
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "priority": self.priority.name,
            "enabled": self.enabled,
            "rules": [r.to_dict() for r in self.rules],
            "metadata": self.metadata.to_dict(),
            # Lineage
            "parent_version": self.parent_version,
            "superseded_by": self.superseded_by,
            # Integrity
            "content_hash": self.content_hash,
            "checksum_verified": self.checksum_verified,
            # Custom
            "custom": self.custom,
            # Timing
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "validated_at": self.validated_at,
            "validated_by": self.validated_by,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "published_at": self.published_at,
            "published_by": self.published_by,
            "activated_at": self.activated_at,
            "activated_by": self.activated_by,
            "superseded_at": self.superseded_at,
            "superseded_by_actor": self.superseded_by_actor,
            "archived_at": self.archived_at,
            "archived_by": self.archived_by,
            "rejected_at": self.rejected_at,
            "rejected_by": self.rejected_by,
            "expired_at": self.expired_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyVersion":
        version = cls(
            version_id=data.get("version_id", ""),
            policy_id=data.get("policy_id", ""),
            version=data.get("version", "0.1.0"),
            status=PolicyLifecycleStatus[data.get("status", "DRAFT")],
            version_status=VersionStatus[data.get("version_status", "CURRENT")],
            name=data.get("name", ""),
            description=data.get("description", ""),
            scope=data.get("scope", "GLOBAL"),
            priority=PolicyPriorityLevel[data.get("priority", "NORMAL")],
            enabled=data.get("enabled", True),
            metadata=PolicyMetadata.from_dict(data.get("metadata", {})),
            parent_version=data.get("parent_version"),
            superseded_by=data.get("superseded_by"),
            content_hash=data.get("content_hash", ""),
            checksum_verified=data.get("checksum_verified", False),
            custom=data.get("custom", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            created_by=data.get("created_by", "SYSTEM"),
            validated_at=data.get("validated_at"),
            validated_by=data.get("validated_by"),
            approved_at=data.get("approved_at"),
            approved_by=data.get("approved_by"),
            published_at=data.get("published_at"),
            published_by=data.get("published_by"),
            activated_at=data.get("activated_at"),
            activated_by=data.get("activated_by"),
            superseded_at=data.get("superseded_at"),
            superseded_by_actor=data.get("superseded_by_actor"),
            archived_at=data.get("archived_at"),
            archived_by=data.get("archived_by"),
            rejected_at=data.get("rejected_at"),
            rejected_by=data.get("rejected_by"),
            expired_at=data.get("expired_at"),
        )
        for rd in data.get("rules", []):
            version.add_rule(PolicyRule.from_dict(rd))
        return version

    def __repr__(self) -> str:
        return (
            f"PolicyVersion(id={self.version_id}, policy={self.policy_id}, "
            f"v={self.version}, status={self.status.name})"
        )
