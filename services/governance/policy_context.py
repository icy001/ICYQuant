"""
Policy Context — extended DecisionContext for versioned policy evaluation.

Extends the base DecisionContext with version-aware tracking: which policy
version was evaluated, snapshot of context at evaluation time, and
evaluation metadata for audit trails.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .decision_context import DecisionContext
from .policy_scope import PolicyScope, PolicyScopeConstants


# ---------------------------------------------------------------------------
# Extended context for versioned evaluation
# ---------------------------------------------------------------------------

@dataclass
class PolicyEvaluationContext:
    """
    Context enriched for versioned policy evaluation.

    Wraps the base DecisionContext with policy-version-specific metadata:
      - Which policy version is being evaluated
      - Snapshot of all metrics at evaluation time (for deterministic replay)
      - Scope resolution cache
      - Evaluation metadata for auditability
    """

    # Identity
    context_id: str = field(
        default_factory=lambda: f"PEC-{uuid.uuid4().hex[:8]}"
    )

    # Wrapped base context
    base_context: DecisionContext = field(default_factory=DecisionContext)

    # Current evaluation target
    policy_id: str = ""
    version_id: str = ""
    scope: str = PolicyScopeConstants.GLOBAL
    scope_qualifier: str = ""

    # Metrics snapshot at evaluation time
    metrics_snapshot: Dict[str, Any] = field(default_factory=dict)

    # Scope resolution cache (keyed by scope string → set of version_ids)
    scope_cache: Dict[str, Dict[str, bool]] = field(default_factory=dict)

    # Evaluation metadata
    evaluation_id: str = ""
    evaluation_order: int = 0  # Order in which this context was evaluated
    parent_evaluation_id: str = ""  # For nested/sub-evaluations
    evaluation_depth: int = 0

    # Timing
    created_at: float = field(default_factory=time.time)
    evaluation_started_at: Optional[float] = None
    evaluation_completed_at: Optional[float] = None

    # Flags
    snapshot_frozen: bool = False  # Once frozen, metrics snapshot is immutable
    cache_enabled: bool = True

    # Custom extensibility
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Context creation
    # ------------------------------------------------------------------

    @classmethod
    def from_decision_context(
        cls,
        base: DecisionContext,
        policy_id: str = "",
        version_id: str = "",
        scope: str = PolicyScopeConstants.GLOBAL,
        scope_qualifier: str = "",
        **kwargs,
    ) -> "PolicyEvaluationContext":
        """Create from a base DecisionContext with policy targeting."""
        return cls(
            base_context=base,
            policy_id=policy_id,
            version_id=version_id,
            scope=scope,
            scope_qualifier=scope_qualifier,
            metrics_snapshot=dict(base.to_dict()),
            **kwargs,
        )

    @classmethod
    def for_policy_version(
        cls,
        base: DecisionContext,
        policy_id: str,
        version_id: str,
        scope: str = PolicyScopeConstants.GLOBAL,
        **kwargs,
    ) -> "PolicyEvaluationContext":
        """Create a context specifically for evaluating one policy version."""
        return cls.from_decision_context(
            base=base,
            policy_id=policy_id,
            version_id=version_id,
            scope=scope,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Metric access
    # ------------------------------------------------------------------

    def get_metric(self, metric: str, default: Any = None) -> Any:
        """Resolve a metric value from the snapshot or base context."""
        # Check snapshot first
        if metric in self.metrics_snapshot:
            return self.metrics_snapshot[metric]

        # Try nested resolution via base context
        ctx_dict = self.base_context.to_dict()
        if metric in ctx_dict:
            return ctx_dict[metric]

        if "." in metric:
            parts = metric.split(".")
            current = ctx_dict
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

        return default

    def get_metrics(self, *metrics: str) -> Dict[str, Any]:
        """Bulk resolve multiple metrics."""
        return {m: self.get_metric(m) for m in metrics}

    def has_metric(self, metric: str) -> bool:
        """Check if a metric exists."""
        return self.get_metric(metric) is not None

    # ------------------------------------------------------------------
    # Snapshot management
    # ------------------------------------------------------------------

    def freeze_snapshot(self) -> "PolicyEvaluationContext":
        """
        Freeze the current metrics snapshot for deterministic replay.

        After freezing, the snapshot cannot be modified. This ensures
        that replaying the evaluation yields the same result.
        """
        if not self.snapshot_frozen:
            self.snapshot_frozen = True
            self.metrics_snapshot = dict(self.base_context.to_dict())
        return self

    def snapshot_hash(self) -> str:
        """Compute a deterministic hash of the frozen snapshot."""
        serialized = json.dumps(
            self.metrics_snapshot, sort_keys=True, default=str
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def update_metric(self, key: str, value: Any) -> None:
        """Update a metric in the snapshot (only if not frozen)."""
        if self.snapshot_frozen:
            raise ValueError("Cannot update frozen metrics snapshot.")
        self.metrics_snapshot[key] = value

    # ------------------------------------------------------------------
    # Scope resolution
    # ------------------------------------------------------------------

    def scope_applies(
        self, policy_scope: PolicyScope, scope_str: str, qualifier: str = ""
    ) -> bool:
        """
        Check if a policy scope applies to the current context scope.
        Results are cached for performance.
        """
        cache_key = f"{policy_scope.scope}:{scope_str}:{qualifier}"
        if self.cache_enabled and cache_key in self.scope_cache:
            return self.scope_cache[cache_key].get("applies", False)

        result = policy_scope.applies_to(scope_str, qualifier)

        if self.cache_enabled:
            self.scope_cache[cache_key] = {"applies": result}

        return result

    def clear_scope_cache(self) -> None:
        """Clear the scope resolution cache."""
        self.scope_cache.clear()

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def start_evaluation(self) -> "PolicyEvaluationContext":
        """Mark the start of evaluation."""
        self.evaluation_started_at = time.time()
        return self

    def complete_evaluation(self) -> "PolicyEvaluationContext":
        """Mark evaluation as complete."""
        self.evaluation_completed_at = time.time()
        return self

    @property
    def evaluation_duration_ms(self) -> float:
        """Duration of evaluation in milliseconds."""
        if self.evaluation_started_at is None:
            return 0.0
        end = self.evaluation_completed_at or time.time()
        return (end - self.evaluation_started_at) * 1000

    # ------------------------------------------------------------------
    # Child context
    # ------------------------------------------------------------------

    def create_child(
        self,
        policy_id: str = "",
        version_id: str = "",
        scope: str = "",
    ) -> "PolicyEvaluationContext":
        """Create a child context for nested evaluation."""
        child = PolicyEvaluationContext(
            base_context=self.base_context,
            policy_id=policy_id or self.policy_id,
            version_id=version_id or self.version_id,
            scope=scope or self.scope,
            metrics_snapshot=dict(self.metrics_snapshot),
            parent_evaluation_id=self.evaluation_id or self.context_id,
            evaluation_depth=self.evaluation_depth + 1,
            cache_enabled=self.cache_enabled,
        )
        return child

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "base_context": self.base_context.to_dict(),
            "policy_id": self.policy_id,
            "version_id": self.version_id,
            "scope": self.scope,
            "scope_qualifier": self.scope_qualifier,
            "metrics_snapshot": self.metrics_snapshot,
            "evaluation_id": self.evaluation_id,
            "evaluation_order": self.evaluation_order,
            "evaluation_depth": self.evaluation_depth,
            "snapshot_frozen": self.snapshot_frozen,
            "evaluation_started_at": self.evaluation_started_at,
            "evaluation_completed_at": self.evaluation_completed_at,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyEvaluationContext":
        return cls(
            context_id=data.get("context_id", ""),
            base_context=DecisionContext.from_dict(
                data.get("base_context", {})
            ),
            policy_id=data.get("policy_id", ""),
            version_id=data.get("version_id", ""),
            scope=data.get("scope", PolicyScopeConstants.GLOBAL),
            scope_qualifier=data.get("scope_qualifier", ""),
            metrics_snapshot=data.get("metrics_snapshot", {}),
            evaluation_id=data.get("evaluation_id", ""),
            evaluation_order=data.get("evaluation_order", 0),
            evaluation_depth=data.get("evaluation_depth", 0),
            snapshot_frozen=data.get("snapshot_frozen", False),
            evaluation_started_at=data.get("evaluation_started_at"),
            evaluation_completed_at=data.get("evaluation_completed_at"),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )

    # ------------------------------------------------------------------
    # Python protocols
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"PolicyEvaluationContext(id={self.context_id}, "
            f"policy={self.policy_id}, version={self.version_id}, "
            f"scope={self.scope}, frozen={self.snapshot_frozen})"
        )

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to metrics."""
        return self.get_metric(key)

    def __contains__(self, key: str) -> bool:
        return self.has_metric(key)


# ---------------------------------------------------------------------------
# Context comparison / diff
# ---------------------------------------------------------------------------

@dataclass
class ContextDiff:
    """
    Diff between two policy evaluation contexts.

    Useful for impact analysis: "what changed between version X and Y?"
    """

    context_a: PolicyEvaluationContext
    context_b: PolicyEvaluationContext

    added: Dict[str, Any] = field(default_factory=dict)
    removed: Dict[str, Any] = field(default_factory=dict)
    changed: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unchanged_count: int = 0

    def __post_init__(self):
        self._compute_diff()

    def _compute_diff(self) -> None:
        """Compute the diff between the two contexts' metric snapshots."""
        a_metrics = self.context_a.metrics_snapshot
        b_metrics = self.context_b.metrics_snapshot

        all_keys = set(a_metrics.keys()) | set(b_metrics.keys())

        for key in sorted(all_keys):
            in_a = key in a_metrics
            in_b = key in b_metrics

            if not in_a:
                self.added[key] = b_metrics[key]
            elif not in_b:
                self.removed[key] = a_metrics[key]
            elif a_metrics[key] != b_metrics[key]:
                self.changed[key] = {
                    "old": a_metrics[key],
                    "new": b_metrics[key],
                }
            else:
                self.unchanged_count += 1

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    @property
    def change_count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)

    def summary(self) -> str:
        """Human-readable diff summary."""
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} added: {list(self.added.keys())}")
        if self.removed:
            parts.append(f"-{len(self.removed)} removed: {list(self.removed.keys())}")
        if self.changed:
            parts.append(f"~{len(self.changed)} changed: {list(self.changed.keys())}")
        if not parts:
            parts.append("no changes")
        return "; ".join(parts)
