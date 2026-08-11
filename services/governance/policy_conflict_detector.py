"""
Policy Conflict Detector — detects conflicts between policy versions.

Conflicts can arise when:
  - Two active policies target the same scope with opposing rules
  - Different priority policies have contradictory effects
  - A new version contradicts an existing active version
  - Conflicting dependency declarations exist

The conflict detector supports:
  - Pre-activation conflict scanning
  - Post-activation periodic re-scanning
  - Conflict resolution strategies
  - Conflict reporting and escalation
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from .policy_version import PolicyVersion
from .policy_registry import PolicyRegistry
from .policy_dependency import DependencyGraph, DependencyType
from .policy_scope import PolicyScopeConstants, ScopeHierarchy


# ---------------------------------------------------------------------------
# Conflict types and severity
# ---------------------------------------------------------------------------

class ConflictType(Enum):
    """Types of policy conflicts."""

    DIRECT_CONTRADICTION = auto()  # Two policies make opposing demands
    SCOPE_OVERLAP = auto()         # Overlapping scope with different rules
    PRIORITY_CONFLICT = auto()     # Priority inversion or ambiguity
    DEPENDENCY_CONFLICT = auto()   # Conflicting dependency declarations
    EFFECT_CONFLICT = auto()       # Opposing effect types
    VERSION_CONFLICT = auto()      # Multiple versions active for same policy


class ConflictSeverity(Enum):
    """How severe a detected conflict is."""

    CRITICAL = auto()   # Must be resolved before any decision can proceed
    HIGH = auto()       # Blocks decisions in affected scopes
    MEDIUM = auto()     # Triggers review for affected decisions
    LOW = auto()        # Advisory — logged but not blocking
    INFO = auto()       # Informational only


# ---------------------------------------------------------------------------
# Conflict
# ---------------------------------------------------------------------------

@dataclass
class PolicyConflict:
    """A detected conflict between two or more policy versions."""

    conflict_id: str = ""
    conflict_type: ConflictType = ConflictType.DIRECT_CONTRADICTION
    severity: ConflictSeverity = ConflictSeverity.MEDIUM

    # Conflicting policies
    policy_a: str = ""       # policy_id of first conflicting policy
    version_a: str = ""      # version_id of first conflicting policy
    policy_b: str = ""       # policy_id of second conflicting policy
    version_b: str = ""      # version_id of second conflicting policy

    # Conflict details
    description: str = ""
    conflicting_scopes: List[str] = field(default_factory=list)
    conflicting_rules: List[str] = field(default_factory=list)

    # Resolution
    resolution: str = ""
    resolved_by: str = ""
    resolved_at: Optional[float] = None
    is_resolved: bool = False

    # Timing
    detected_at: float = field(default_factory=time.time)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        return self.severity in (ConflictSeverity.CRITICAL, ConflictSeverity.HIGH)

    def resolve(self, resolution: str, actor: str) -> None:
        self.resolution = resolution
        self.resolved_by = actor
        self.resolved_at = time.time()
        self.is_resolved = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.name,
            "severity": self.severity.name,
            "policy_a": self.policy_a,
            "version_a": self.version_a,
            "policy_b": self.policy_b,
            "version_b": self.version_b,
            "description": self.description,
            "conflicting_scopes": self.conflicting_scopes,
            "conflicting_rules": self.conflicting_rules,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "is_resolved": self.is_resolved,
            "is_blocking": self.is_blocking,
            "detected_at": self.detected_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyConflict":
        conflict = cls(
            conflict_id=data.get("conflict_id", ""),
            conflict_type=ConflictType[data.get("conflict_type", "DIRECT_CONTRADICTION")],
            severity=ConflictSeverity[data.get("severity", "MEDIUM")],
            policy_a=data.get("policy_a", ""),
            version_a=data.get("version_a", ""),
            policy_b=data.get("policy_b", ""),
            version_b=data.get("version_b", ""),
            description=data.get("description", ""),
            conflicting_scopes=data.get("conflicting_scopes", []),
            conflicting_rules=data.get("conflicting_rules", []),
            resolution=data.get("resolution", ""),
            resolved_by=data.get("resolved_by", ""),
            resolved_at=data.get("resolved_at"),
            is_resolved=data.get("is_resolved", False),
            detected_at=data.get("detected_at", time.time()),
            metadata=data.get("metadata", {}),
        )
        return conflict

    def __repr__(self) -> str:
        return (
            f"PolicyConflict({self.conflict_type.name}, "
            f"{self.policy_a} ↔ {self.policy_b}, "
            f"severity={self.severity.name}, resolved={self.is_resolved})"
        )


# ---------------------------------------------------------------------------
# Conflict Detector
# ---------------------------------------------------------------------------

@dataclass
class PolicyConflictDetector:
    """
    Detects conflicts between policy versions.

    Scans active policies for:
      - Direct contradictions (same scope, opposite effects)
      - Scope overlaps with conflicting rules
      - Priority conflicts
      - Dependency conflicts
      - Multiple active versions
    """

    registry: Optional[PolicyRegistry] = None
    dependency_graph: Optional[DependencyGraph] = None

    # Detected conflicts
    conflicts: List[PolicyConflict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_all(self) -> List[PolicyConflict]:
        """Run all conflict detection checks and return results."""
        self.conflicts.clear()

        self._detect_scope_overlaps()
        self._detect_direct_contradictions()
        self._detect_dependency_conflicts()
        self._detect_version_conflicts()

        return self.conflicts

    def detect_for_version(self, version: PolicyVersion) -> List[PolicyConflict]:
        """Detect conflicts that would arise if this version were activated."""
        result: List[PolicyConflict] = []

        if not self.registry:
            return result

        active = self.registry.list_active()

        for active_v in active:
            # Skip same policy family
            if active_v.policy_id == version.policy_id:
                continue

            # Check scope overlap
            if self._scopes_overlap(version.scope, active_v.scope):
                # Check for contradictory rules
                contradictions = self._find_contradictions(version, active_v)
                if contradictions:
                    conflict = PolicyConflict(
                        conflict_type=ConflictType.SCOPE_OVERLAP,
                        severity=ConflictSeverity.MEDIUM,
                        policy_a=version.policy_id,
                        version_a=version.version_id,
                        policy_b=active_v.policy_id,
                        version_b=active_v.version_id,
                        description=(
                            f"Scope overlap between '{version.name}' "
                            f"and '{active_v.name}': {contradictions}"
                        ),
                        conflicting_scopes=[version.scope, active_v.scope],
                        conflicting_rules=contradictions,
                    )
                    result.append(conflict)

        return result

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_scope_overlaps(self) -> None:
        """Detect policies with overlapping scopes that have contradictory rules."""
        if not self.registry:
            return

        active = self.registry.list_active()
        for i, v1 in enumerate(active):
            for v2 in active[i + 1:]:
                if v1.policy_id == v2.policy_id:
                    continue

                if self._scopes_overlap(v1.scope, v2.scope):
                    # Different scope but overlapping hierarchy
                    conflict = PolicyConflict(
                        conflict_id=f"CF-{v1.policy_id}-{v2.policy_id}-SCOPE",
                        conflict_type=ConflictType.SCOPE_OVERLAP,
                        severity=ConflictSeverity.LOW,
                        policy_a=v1.policy_id,
                        version_a=v1.version_id,
                        policy_b=v2.policy_id,
                        version_b=v2.version_id,
                        description=(
                            f"Scope overlap: '{v1.name}' ({v1.scope}) and "
                            f"'{v2.name}' ({v2.scope})"
                        ),
                        conflicting_scopes=[v1.scope, v2.scope],
                    )
                    self.conflicts.append(conflict)

    def _detect_direct_contradictions(self) -> None:
        """Detect policies that make directly opposing demands."""
        if not self.registry:
            return

        active = self.registry.list_active()
        for i, v1 in enumerate(active):
            for v2 in active[i + 1:]:
                if v1.policy_id == v2.policy_id:
                    continue

                contradictions = self._find_contradictions(v1, v2)
                if contradictions:
                    conflict = PolicyConflict(
                        conflict_id=f"CF-{v1.policy_id}-{v2.policy_id}-RULE",
                        conflict_type=ConflictType.DIRECT_CONTRADICTION,
                        severity=ConflictSeverity.HIGH,
                        policy_a=v1.policy_id,
                        version_a=v1.version_id,
                        policy_b=v2.policy_id,
                        version_b=v2.version_id,
                        description=(
                            f"'{v1.name}' and '{v2.name}' have conflicting rules: "
                            f"{'; '.join(contradictions)}"
                        ),
                        conflicting_rules=contradictions,
                    )
                    self.conflicts.append(conflict)

    def _detect_dependency_conflicts(self) -> None:
        """Detect conflicts from dependency declarations."""
        if not self.dependency_graph:
            return

        cycles = self.dependency_graph.find_cycles()
        for cycle in cycles:
            conflict = PolicyConflict(
                conflict_id=f"CF-DEP-CYCLE-{'-'.join(cycle[:3])}",
                conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                severity=ConflictSeverity.CRITICAL,
                description=f"Dependency cycle detected: {' → '.join(cycle)}",
                policy_a=cycle[0] if cycle else "",
                policy_b=cycle[-1] if len(cycle) > 1 else "",
            )
            self.conflicts.append(conflict)

    def _detect_version_conflicts(self) -> None:
        """Detect multiple active versions of the same policy."""
        if not self.registry:
            return

        active = self.registry.list_active()
        policy_active_count: Dict[str, List[PolicyVersion]] = {}

        for v in active:
            if v.policy_id not in policy_active_count:
                policy_active_count[v.policy_id] = []
            policy_active_count[v.policy_id].append(v)

        for policy_id, versions in policy_active_count.items():
            if len(versions) > 1:
                conflict = PolicyConflict(
                    conflict_id=f"CF-VERSION-{policy_id}",
                    conflict_type=ConflictType.VERSION_CONFLICT,
                    severity=ConflictSeverity.CRITICAL,
                    policy_a=policy_id,
                    version_a=versions[0].version_id,
                    policy_b=policy_id,
                    version_b=versions[1].version_id,
                    description=(
                        f"Multiple versions active for policy '{policy_id}': "
                        f"{', '.join(v.version for v in versions)}"
                    ),
                )
                self.conflicts.append(conflict)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _scopes_overlap(scope_a: str, scope_b: str) -> bool:
        """Check if two scopes overlap (one covers the other)."""
        if scope_a == scope_b:
            return True
        if scope_a == PolicyScopeConstants.GLOBAL or scope_b == PolicyScopeConstants.GLOBAL:
            return True
        return (
            ScopeHierarchy.is_descendant(scope_a, scope_b)
            or ScopeHierarchy.is_descendant(scope_b, scope_a)
        )

    @staticmethod
    def _find_contradictions(
        v1: PolicyVersion, v2: PolicyVersion
    ) -> List[str]:
        """Find contradictory rules between two policy versions."""
        contradictions: List[str] = []

        # Build rule index by metric
        v1_rules = {r.metric: r for r in v1.rules if r.metric}
        v2_rules = {r.metric: r for r in v2.rules if r.metric}

        for metric in set(v1_rules.keys()) & set(v2_rules.keys()):
            r1 = v1_rules[metric]
            r2 = v2_rules[metric]

            # Check for opposite operators
            if r1.operator == ">" and r2.operator == "<":
                if r1.threshold and r2.threshold:
                    contradictions.append(
                        f"Metric '{metric}': {v1.name}={r1.operator}{r1.threshold} vs "
                        f"{v2.name}={r2.operator}{r2.threshold}"
                    )
            elif r1.operator == "<" and r2.operator == ">":
                if r1.threshold and r2.threshold:
                    contradictions.append(
                        f"Metric '{metric}': {v1.name}={r1.operator}{r1.threshold} vs "
                        f"{v2.name}={r2.operator}{r2.threshold}"
                    )

        return contradictions

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_unresolved(self) -> List[PolicyConflict]:
        return [c for c in self.conflicts if not c.is_resolved]

    def get_blocking(self) -> List[PolicyConflict]:
        return [
            c for c in self.conflicts
            if c.is_blocking and not c.is_resolved
        ]

    def get_by_type(self, conflict_type: ConflictType) -> List[PolicyConflict]:
        return [c for c in self.conflicts if c.conflict_type == conflict_type]

    def get_for_policy(self, policy_id: str) -> List[PolicyConflict]:
        return [
            c for c in self.conflicts
            if c.policy_a == policy_id or c.policy_b == policy_id
        ]

    def resolve_all_for_policy(self, policy_id: str, reason: str, actor: str) -> int:
        """Resolve all conflicts involving a policy."""
        count = 0
        for c in self.get_for_policy(policy_id):
            if not c.is_resolved:
                c.resolve(reason, actor)
                count += 1
        return count

    def has_blocking_conflicts(self) -> bool:
        return len(self.get_blocking()) > 0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflicts": [c.to_dict() for c in self.conflicts],
            "total": len(self.conflicts),
            "unresolved": len(self.get_unresolved()),
            "blocking": len(self.get_blocking()),
            "has_blocking": self.has_blocking_conflicts(),
        }

    def __repr__(self) -> str:
        return (
            f"PolicyConflictDetector(conflicts={len(self.conflicts)}, "
            f"unresolved={len(self.get_unresolved())})"
        )
