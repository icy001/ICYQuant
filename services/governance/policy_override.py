"""
Policy Override — manual and emergency overrides for policy evaluations.

Overrides allow authorized actors to temporarily or permanently bypass
specific policies under controlled, fully audited conditions.

Override types:
  - MANUAL: Explicit human override with justification.
  - EMERGENCY: Emergency override (wider scope, shorter duration).
  - SCHEDULED: Pre-planned override window.
  - CONDITIONAL: Override only when specific conditions are met.
  - PERMANENT: One-time permanent policy exemption.

Design principles:
  - Every override is recorded in the audit trail.
  - Overrides have explicit expiry.
  - Emergency overrides require higher authority.
  - Overrides can be chained but not recursive.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .policy_priority import PolicyPriorityLevel


# ---------------------------------------------------------------------------
# Override types
# ---------------------------------------------------------------------------

class OverrideType(Enum):
    """Type of policy override."""

    MANUAL = auto()       # Human-initiated override
    EMERGENCY = auto()    # Emergency override (break-glass)
    SCHEDULED = auto()    # Pre-scheduled override window
    CONDITIONAL = auto()  # Condition-based override
    PERMANENT = auto()    # Permanent exemption
    TEMPORARY = auto()    # Time-limited override


class OverrideStatus(Enum):
    """Status of an override."""

    PENDING = auto()     # Created but not yet active
    ACTIVE = auto()      # Currently in effect
    EXPIRED = auto()     # Past its expiry
    REVOKED = auto()     # Explicitly revoked
    APPLIED = auto()     # One-time override has been applied
    REJECTED = auto()    # Override request was rejected


# ---------------------------------------------------------------------------
# Override request and result
# ---------------------------------------------------------------------------

@dataclass
class PolicyOverride:
    """
    A formal override record for bypassing a specific policy.

    Each override:
      - Targets a specific policy (or scope of policies)
      - Has an actor, reason, and approval chain
      - Has an explicit validity window
      - Is fully auditable
    """

    override_id: str = field(
        default_factory=lambda: f"OVR-{uuid.uuid4().hex[:12]}"
    )

    # Target
    target_policy_id: str = ""        # Policy to override (empty = all)
    target_version_id: str = ""       # Specific version to override
    target_scope: str = ""            # Override policies in a scope
    target_rule_ids: List[str] = field(default_factory=list)  # Specific rules

    # Type and status
    override_type: OverrideType = OverrideType.MANUAL
    status: OverrideStatus = OverrideStatus.PENDING

    # Actor
    actor: str = ""                   # Who requested/created the override
    approver: str = ""                # Who approved the override
    approval_chain: List[str] = field(default_factory=list)

    # Justification
    reason: str = ""                  # Business justification
    reference: str = ""               # Ticket/incident/PR reference
    impact_assessment: str = ""       # Assessment of impact

    # Validity window
    effective_from: float = field(default_factory=time.time)
    effective_until: Optional[float] = None
    max_uses: int = 0                 # 0 = unlimited
    use_count: int = 0

    # Scope limitation
    restricted_scopes: List[str] = field(default_factory=list)
    restricted_decision_types: List[str] = field(default_factory=list)

    # Override behavior
    new_effect: str = ""  # What effect to apply instead (ALLOW, WARN, etc.)
    reason_required: bool = True  # Require reason on each application

    # Emergency-specific
    emergency_level: int = 0
    auto_expire_hours: int = 0  # Hours after which emergency override auto-expires

    # Timing
    created_at: float = field(default_factory=time.time)
    activated_at: Optional[float] = None
    expired_at: Optional[float] = None
    revoked_at: Optional[float] = None
    revoked_by: str = ""
    revoke_reason: str = ""

    # Audit
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(self, actor: str = "") -> "PolicyOverride":
        """Activate this override."""
        if self.status != OverrideStatus.PENDING:
            raise ValueError(
                f"Cannot activate override in status {self.status.name}"
            )
        self.status = OverrideStatus.ACTIVE
        self.activated_at = time.time()
        self._audit("ACTIVATED", actor, "Override activated")
        return self

    def apply(self, context: Dict[str, Any]) -> bool:
        """
        Apply this override to a context.
        Returns True if override was successfully applied.
        """
        if not self.is_effective():
            return False

        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False

        self.use_count += 1
        self._audit("APPLIED", "", f"Override applied (use {self.use_count})")

        # Auto-expire if max uses reached
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            self.expire("Max uses reached")

        return True

    def expire(self, reason: str = "") -> "PolicyOverride":
        """Mark as expired."""
        self.status = OverrideStatus.EXPIRED
        self.expired_at = time.time()
        self._audit("EXPIRED", "", reason or "Override expired")
        return self

    def revoke(self, actor: str, reason: str = "") -> "PolicyOverride":
        """Revoke this override."""
        self.status = OverrideStatus.REVOKED
        self.revoked_at = time.time()
        self.revoked_by = actor
        self.revoke_reason = reason
        self._audit("REVOKED", actor, reason or "Override revoked")
        return self

    def reject(self, actor: str, reason: str = "") -> "PolicyOverride":
        """Reject an override request."""
        self.status = OverrideStatus.REJECTED
        self._audit("REJECTED", actor, reason or "Override rejected")
        return self

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_effective(self, now: Optional[float] = None) -> bool:
        """Check if this override is currently effective."""
        now = now or time.time()

        if self.status != OverrideStatus.ACTIVE:
            return False

        if self.effective_from > now:
            return False

        if self.effective_until is not None and self.effective_until < now:
            return False

        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False

        return True

    @property
    def is_active(self) -> bool:
        return self.status == OverrideStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        return self.status == OverrideStatus.EXPIRED

    @property
    def is_emergency(self) -> bool:
        return self.override_type == OverrideType.EMERGENCY

    @property
    def applies_to_policy(self, policy_id: str) -> bool:
        """Check if this override applies to a given policy."""
        if not self.target_policy_id:
            return True  # Applies to all
        return self.target_policy_id == policy_id

    def applies_to_rule(self, rule_id: str) -> bool:
        """Check if this override applies to a given rule."""
        if not self.target_rule_ids:
            return True  # Applies to all rules
        return rule_id in self.target_rule_ids

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _audit(self, action: str, actor: str, detail: str) -> None:
        self.audit_log.append({
            "action": action,
            "actor": actor,
            "detail": detail,
            "timestamp": time.time(),
        })

    def time_remaining_seconds(self, now: Optional[float] = None) -> Optional[float]:
        """Seconds until this override expires, or None if no expiry."""
        if self.effective_until is None:
            return None
        now = now or time.time()
        return max(0, self.effective_until - now)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def emergency(
        cls,
        actor: str,
        reason: str,
        target_policy_id: str = "",
        duration_hours: int = 4,
        **kwargs,
    ) -> "PolicyOverride":
        """Create an emergency override."""
        now = time.time()
        return cls(
            override_type=OverrideType.EMERGENCY,
            actor=actor,
            reason=f"[EMERGENCY] {reason}",
            target_policy_id=target_policy_id,
            effective_from=now,
            effective_until=now + duration_hours * 3600,
            emergency_level=1,
            auto_expire_hours=duration_hours,
            new_effect="ALLOW",
            **kwargs,
        )

    @classmethod
    def manual(
        cls,
        actor: str,
        reason: str,
        target_policy_id: str,
        duration_hours: int = 24,
        **kwargs,
    ) -> "PolicyOverride":
        """Create a manual override."""
        now = time.time()
        return cls(
            override_type=OverrideType.MANUAL,
            actor=actor,
            reason=reason,
            target_policy_id=target_policy_id,
            effective_from=now,
            effective_until=now + duration_hours * 3600,
            **kwargs,
        )

    @classmethod
    def permanent_exemption(
        cls,
        actor: str,
        reason: str,
        target_policy_id: str,
        **kwargs,
    ) -> "PolicyOverride":
        """Create a permanent exemption."""
        return cls(
            override_type=OverrideType.PERMANENT,
            actor=actor,
            reason=reason,
            target_policy_id=target_policy_id,
            effective_until=None,  # No expiry
            max_uses=0,  # Unlimited
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "override_id": self.override_id,
            "target_policy_id": self.target_policy_id,
            "target_version_id": self.target_version_id,
            "target_scope": self.target_scope,
            "target_rule_ids": self.target_rule_ids,
            "override_type": self.override_type.name,
            "status": self.status.name,
            "actor": self.actor,
            "approver": self.approver,
            "approval_chain": self.approval_chain,
            "reason": self.reason,
            "reference": self.reference,
            "impact_assessment": self.impact_assessment,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "max_uses": self.max_uses,
            "use_count": self.use_count,
            "restricted_scopes": self.restricted_scopes,
            "restricted_decision_types": self.restricted_decision_types,
            "new_effect": self.new_effect,
            "reason_required": self.reason_required,
            "emergency_level": self.emergency_level,
            "auto_expire_hours": self.auto_expire_hours,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "expired_at": self.expired_at,
            "revoked_at": self.revoked_at,
            "revoked_by": self.revoked_by,
            "revoke_reason": self.revoke_reason,
            "audit_log": self.audit_log,
            "is_active": self.is_active,
            "is_effective": self.is_effective(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyOverride":
        return cls(
            override_id=data.get("override_id", ""),
            target_policy_id=data.get("target_policy_id", ""),
            target_version_id=data.get("target_version_id", ""),
            target_scope=data.get("target_scope", ""),
            target_rule_ids=data.get("target_rule_ids", []),
            override_type=OverrideType[data.get("override_type", "MANUAL")],
            status=OverrideStatus[data.get("status", "PENDING")],
            actor=data.get("actor", ""),
            approver=data.get("approver", ""),
            approval_chain=data.get("approval_chain", []),
            reason=data.get("reason", ""),
            reference=data.get("reference", ""),
            impact_assessment=data.get("impact_assessment", ""),
            effective_from=data.get("effective_from", time.time()),
            effective_until=data.get("effective_until"),
            max_uses=data.get("max_uses", 0),
            use_count=data.get("use_count", 0),
            restricted_scopes=data.get("restricted_scopes", []),
            restricted_decision_types=data.get("restricted_decision_types", []),
            new_effect=data.get("new_effect", ""),
            reason_required=data.get("reason_required", True),
            emergency_level=data.get("emergency_level", 0),
            auto_expire_hours=data.get("auto_expire_hours", 0),
            created_at=data.get("created_at", time.time()),
            activated_at=data.get("activated_at"),
            expired_at=data.get("expired_at"),
            revoked_at=data.get("revoked_at"),
            revoked_by=data.get("revoked_by", ""),
            revoke_reason=data.get("revoke_reason", ""),
            audit_log=data.get("audit_log", []),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"PolicyOverride(id={self.override_id}, type={self.override_type.name}, "
            f"status={self.status.name}, policy={self.target_policy_id})"
        )


# ---------------------------------------------------------------------------
# Override Registry
# ---------------------------------------------------------------------------

@dataclass
class OverrideRegistry:
    """
    Registry of all active and historical overrides.

    Provides:
      - Fast lookup: find overrides applicable to a given policy/rule
      - Conflict detection: detect overlapping overrides
      - Expiry management: auto-expire stale overrides
      - Audit trail: complete history of all overrides
    """

    overrides: Dict[str, PolicyOverride] = field(default_factory=dict)
    _index_by_policy: Dict[str, List[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, override: PolicyOverride) -> None:
        """Register an override."""
        self.overrides[override.override_id] = override
        self._index_override(override)

    def get(self, override_id: str) -> Optional[PolicyOverride]:
        return self.overrides.get(override_id)

    def remove(self, override_id: str) -> None:
        ovr = self.overrides.pop(override_id, None)
        if ovr:
            self._deindex_override(ovr)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def find_for_policy(
        self, policy_id: str, include_expired: bool = False
    ) -> List[PolicyOverride]:
        """Find all overrides applicable to a given policy."""
        candidates: List[str] = []
        # Policy-specific overrides
        candidates.extend(self._index_by_policy.get(policy_id, []))
        # Global overrides (no target_policy_id)
        candidates.extend(self._index_by_policy.get("*", []))

        results = []
        for oid in set(candidates):
            ovr = self.overrides.get(oid)
            if ovr is None:
                continue
            if not include_expired and ovr.is_expired:
                continue
            results.append(ovr)

        return sorted(results, key=lambda o: o.created_at, reverse=True)

    def find_active_for_policy(self, policy_id: str) -> List[PolicyOverride]:
        """Find currently active overrides applicable to a policy."""
        return [
            o for o in self.find_for_policy(policy_id)
            if o.is_effective()
        ]

    def find_for_rule(
        self, policy_id: str, rule_id: str
    ) -> List[PolicyOverride]:
        """Find active overrides applicable to a specific rule."""
        active = self.find_active_for_policy(policy_id)
        return [
            o for o in active if o.applies_to_rule(rule_id)
        ]

    def is_overridden(
        self, policy_id: str, rule_id: str = "", now: Optional[float] = None
    ) -> bool:
        """Check if a policy/rule is currently overridden."""
        active = self.find_active_for_policy(policy_id)
        for ovr in active:
            if not ovr.is_effective(now):
                continue
            if rule_id and not ovr.applies_to_rule(rule_id):
                continue
            return True
        return False

    def list_active(self) -> List[PolicyOverride]:
        """List all currently active overrides."""
        return [
            o for o in self.overrides.values() if o.is_effective()
        ]

    def list_emergency(self) -> List[PolicyOverride]:
        """List all active emergency overrides."""
        return [
            o for o in self.list_active() if o.is_emergency
        ]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def expire_stale(self, now: Optional[float] = None) -> int:
        """Expire all overrides past their effective_until."""
        now = now or time.time()
        count = 0
        for ovr in list(self.overrides.values()):
            if ovr.is_active and ovr.effective_until and ovr.effective_until < now:
                ovr.expire("Auto-expired")
                count += 1
        return count

    def revoke_all_for_policy(self, policy_id: str, actor: str, reason: str) -> int:
        """Revoke all active overrides for a policy."""
        count = 0
        for ovr in self.find_active_for_policy(policy_id):
            ovr.revoke(actor, reason)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _index_override(self, ovr: PolicyOverride) -> None:
        key = ovr.target_policy_id or "*"
        if key not in self._index_by_policy:
            self._index_by_policy[key] = []
        if ovr.override_id not in self._index_by_policy[key]:
            self._index_by_policy[key].append(ovr.override_id)

    def _deindex_override(self, ovr: PolicyOverride) -> None:
        key = ovr.target_policy_id or "*"
        lst = self._index_by_policy.get(key, [])
        if ovr.override_id in lst:
            lst.remove(ovr.override_id)

    def rebuild_index(self) -> None:
        """Rebuild all indexes from scratch."""
        self._index_by_policy.clear()
        for ovr in self.overrides.values():
            self._index_override(ovr)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overrides": [o.to_dict() for o in self.overrides.values()],
            "active_count": len(self.list_active()),
            "total_count": len(self.overrides),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OverrideRegistry":
        registry = cls()
        for od in data.get("overrides", []):
            registry.register(PolicyOverride.from_dict(od))
        return registry
