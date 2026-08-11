"""
Policy Result — enriched evaluation result from versioned policy evaluation.

Extends the raw evaluation output with version traceability, effect aggregation,
explainability, and structured outcome classification.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .policy_effect import AggregatedEffects, EffectSeverity, EffectType, PolicyEffect
from .policy_priority import PolicyPriorityLevel
from .policy_status import PolicyLifecycleStatus


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

@dataclass
class PolicyOutcome:
    """
    Structured outcome from a single policy version evaluation.

    Classifies the result as one of:
      - ALLOW: All rules passed, no restrictions.
      - INFORM: Policy evaluated, results are informational.
      - WARN: Warnings issued, but no blocking.
      - REVIEW: Requires manual review.
      - RESTRICT: Scope or parameters restricted.
      - BLOCK: Execution blocked.
      - ERROR: Evaluation failed (fail-closed: treated as BLOCK).
    """

    outcome_id: str = field(
        default_factory=lambda: f"OUT-{uuid.uuid4().hex[:8]}"
    )
    classification: str = "ALLOW"  # ALLOW, INFORM, WARN, REVIEW, RESTRICT, BLOCK, ERROR

    policy_id: str = ""
    version_id: str = ""
    version: str = ""
    policy_name: str = ""

    # Evaluation pass/fail
    passed: bool = True
    blocking: bool = False
    blocked_reason: str = ""

    # Counts
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    skipped_rules: int = 0
    total_rule_sets: int = 0
    passed_rule_sets: int = 0

    # Effects
    effects: List[PolicyEffect] = field(default_factory=list)
    aggregated_effects: Optional[AggregatedEffects] = None

    # Priority at time of evaluation
    priority: PolicyPriorityLevel = PolicyPriorityLevel.NORMAL

    # Timing
    evaluation_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    # Explanation
    summary: str = ""
    detail: str = ""

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.aggregated_effects is None and self.effects:
            self.aggregated_effects = AggregatedEffects.aggregate(self.effects)
        if self.aggregated_effects:
            self.classification = self.aggregated_effects.overall_outcome

    @property
    def is_allow(self) -> bool:
        return self.classification == "ALLOW"

    @property
    def is_review(self) -> bool:
        return self.classification == "REVIEW"

    @property
    def is_block(self) -> bool:
        return self.classification == "BLOCK"

    @property
    def is_error(self) -> bool:
        return self.classification == "ERROR"

    @property
    def allows_execution(self) -> bool:
        """Whether execution is allowed based on this outcome."""
        return self.classification in ("ALLOW", "INFORM", "WARN")

    @property
    def requires_action(self) -> bool:
        """Whether human action is required."""
        return self.classification in ("REVIEW", "RESTRICT", "BLOCK")

    @property
    def highest_effect_type(self) -> Optional[str]:
        if not self.effects:
            return None
        severities = sorted(
            self.effects,
            key=lambda e: e.severity.value,
            reverse=True,
        )
        return severities[0].effect_type.name if severities else None

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def passed_result(
        cls,
        policy_id: str = "",
        version_id: str = "",
        version: str = "",
        policy_name: str = "",
        **kwargs,
    ) -> "PolicyOutcome":
        """Create an ALLOW outcome."""
        return cls(
            classification="ALLOW",
            passed=True,
            policy_id=policy_id,
            version_id=version_id,
            version=version,
            policy_name=policy_name,
            summary=f"Policy '{policy_name}' passed",
            **kwargs,
        )

    @classmethod
    def blocked_result(
        cls,
        policy_id: str = "",
        version_id: str = "",
        version: str = "",
        policy_name: str = "",
        reason: str = "",
        effects: Optional[List[PolicyEffect]] = None,
        **kwargs,
    ) -> "PolicyOutcome":
        """Create a BLOCK outcome."""
        if effects is None:
            effects = [
                PolicyEffect.block(
                    source_policy_id=policy_id,
                    source_version_id=version_id,
                    reason=reason,
                )
            ]
        return cls(
            classification="BLOCK",
            passed=False,
            blocking=True,
            policy_id=policy_id,
            version_id=version_id,
            version=version,
            policy_name=policy_name,
            blocked_reason=reason,
            effects=effects,
            summary=f"Blocked by '{policy_name}': {reason}",
            **kwargs,
        )

    @classmethod
    def error_result(
        cls,
        policy_id: str = "",
        version_id: str = "",
        error: str = "",
        **kwargs,
    ) -> "PolicyOutcome":
        """Create an ERROR outcome (fail-closed)."""
        return cls(
            classification="ERROR",
            passed=False,
            blocking=True,
            policy_id=policy_id,
            version_id=version_id,
            blocked_reason=f"Evaluation error: {error}",
            summary=f"Evaluation error in policy '{policy_id}': {error}",
            **kwargs,
        )

    @classmethod
    def review_result(
        cls,
        policy_id: str = "",
        version_id: str = "",
        policy_name: str = "",
        effects: Optional[List[PolicyEffect]] = None,
        **kwargs,
    ) -> "PolicyOutcome":
        """Create a REVIEW outcome."""
        return cls(
            classification="REVIEW",
            passed=True,
            policy_id=policy_id,
            version_id=version_id,
            policy_name=policy_name,
            effects=effects or [],
            summary=f"Policy '{policy_name}' requires review",
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "classification": self.classification,
            "policy_id": self.policy_id,
            "version_id": self.version_id,
            "version": self.version,
            "policy_name": self.policy_name,
            "passed": self.passed,
            "blocking": self.blocking,
            "blocked_reason": self.blocked_reason,
            "total_rules": self.total_rules,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "skipped_rules": self.skipped_rules,
            "total_rule_sets": self.total_rule_sets,
            "passed_rule_sets": self.passed_rule_sets,
            "effects": [e.to_dict() for e in self.effects],
            "aggregated_effects": (
                self.aggregated_effects.to_dict()
                if self.aggregated_effects
                else None
            ),
            "priority": self.priority.name,
            "evaluation_time_ms": self.evaluation_time_ms,
            "summary": self.summary,
            "detail": self.detail,
            "metadata": self.metadata,
            "allows_execution": self.allows_execution,
            "requires_action": self.requires_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyOutcome":
        outcome = cls(
            outcome_id=data.get("outcome_id", ""),
            classification=data.get("classification", "ALLOW"),
            policy_id=data.get("policy_id", ""),
            version_id=data.get("version_id", ""),
            version=data.get("version", ""),
            policy_name=data.get("policy_name", ""),
            passed=data.get("passed", True),
            blocking=data.get("blocking", False),
            blocked_reason=data.get("blocked_reason", ""),
            total_rules=data.get("total_rules", 0),
            passed_rules=data.get("passed_rules", 0),
            failed_rules=data.get("failed_rules", 0),
            skipped_rules=data.get("skipped_rules", 0),
            total_rule_sets=data.get("total_rule_sets", 0),
            passed_rule_sets=data.get("passed_rule_sets", 0),
            priority=PolicyPriorityLevel[data.get("priority", "NORMAL")],
            evaluation_time_ms=data.get("evaluation_time_ms", 0.0),
            summary=data.get("summary", ""),
            detail=data.get("detail", ""),
            metadata=data.get("metadata", {}),
        )
        for ed in data.get("effects", []):
            outcome.effects.append(PolicyEffect.from_dict(ed))
        if outcome.effects:
            outcome.aggregated_effects = AggregatedEffects.aggregate(
                outcome.effects
            )
        return outcome

    def __repr__(self) -> str:
        return (
            f"PolicyOutcome({self.classification}, policy={self.policy_id}, "
            f"v={self.version}, passed={self.passed})"
        )


# ---------------------------------------------------------------------------
# Versioned policy evaluation result (aggregate of outcomes)
# ---------------------------------------------------------------------------

@dataclass
class VersionedPolicyResult:
    """
    Aggregate result of evaluating a set of versioned policies.

    This is the consumable output from a policy evaluation run:
      - Aggregated verdict (ALLOW / REVIEW / BLOCK)
      - Per-policy outcomes with full traceability
      - Effect aggregation across all policies
      - Explainable decision: why exactly was this blocked/allowed?
    """

    decision_id: str = ""
    request_id: str = ""

    # Aggregate verdict
    overall_verdict: str = "ALLOW"  # ALLOW, REVIEW, BLOCK
    execution_allowed: bool = True
    review_required: bool = False

    # Per-policy outcomes (ordered by evaluation sequence)
    outcomes: List[PolicyOutcome] = field(default_factory=list)

    # Aggregate effects across all policies
    all_effects: List[PolicyEffect] = field(default_factory=list)
    aggregated_effects: Optional[AggregatedEffects] = None

    # Stats
    policies_evaluated: int = 0
    policies_passed: int = 0
    policies_blocked: int = 0
    policies_errored: int = 0
    policies_skipped: int = 0
    total_evaluation_time_ms: float = 0.0

    # Policy version info from evaluation
    active_versions: List[Dict[str, str]] = field(default_factory=list)

    # Explainability
    decision_explanation: str = ""
    blocking_reasons: List[str] = field(default_factory=list)
    review_reasons: List[str] = field(default_factory=list)

    # Timing
    timestamp: float = field(default_factory=time.time)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.outcomes:
            self._recompute()

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _recompute(self) -> None:
        """Recompute aggregate stats from outcomes."""
        self.all_effects = []
        self.blocking_reasons = []
        self.review_reasons = []
        self.policies_evaluated = len(self.outcomes)
        self.policies_passed = 0
        self.policies_blocked = 0
        self.policies_errored = 0
        self.policies_skipped = 0

        for outcome in self.outcomes:
            if outcome.is_block:
                self.policies_blocked += 1
                self.blocking_reasons.append(outcome.blocked_reason or outcome.summary)
            elif outcome.is_error:
                self.policies_errored += 1
                self.blocking_reasons.append(outcome.blocked_reason or f"Error: {outcome.policy_id}")
            elif outcome.is_review:
                self.review_reasons.append(outcome.summary)
            elif outcome.is_allow:
                self.policies_passed += 1
            else:
                self.policies_passed += 1

            self.all_effects.extend(outcome.effects)

        # Aggregate all effects
        if self.all_effects:
            self.aggregated_effects = AggregatedEffects.aggregate(self.all_effects)

        # Determine overall verdict
        if self.policies_blocked > 0 or self.policies_errored > 0:
            self.overall_verdict = "BLOCK"
            self.execution_allowed = False
            self.review_required = False
        elif self.review_reasons:
            self.overall_verdict = "REVIEW"
            self.execution_allowed = False
            self.review_required = True
        else:
            self.overall_verdict = "ALLOW"
            self.execution_allowed = True
            self.review_required = False

        # Build explanation
        self._build_explanation()

    def add_outcome(self, outcome: PolicyOutcome) -> "VersionedPolicyResult":
        """Add a policy outcome and recompute aggregate stats."""
        self.outcomes.append(outcome)
        self._recompute()
        return self

    def add_outcomes(self, *outcomes: PolicyOutcome) -> "VersionedPolicyResult":
        """Add multiple outcomes at once."""
        self.outcomes.extend(outcomes)
        self._recompute()
        return self

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    def _build_explanation(self) -> None:
        """Build a human-readable explanation of the decision."""
        parts = []

        if self.overall_verdict == "ALLOW":
            parts.append(
                f"Decision ALLOWED after evaluating {self.policies_evaluated} policies "
                f"({self.policies_passed} passed, {self.policies_blocked} blocked, "
                f"{self.policies_errored} errored)."
            )
        elif self.overall_verdict == "BLOCK":
            parts.append(
                f"Decision BLOCKED by {self.policies_blocked + self.policies_errored} "
                f"policies:"
            )
            for reason in self.blocking_reasons[:5]:
                parts.append(f"  - {reason}")
            if len(self.blocking_reasons) > 5:
                parts.append(f"  ... and {len(self.blocking_reasons) - 5} more")
        elif self.overall_verdict == "REVIEW":
            parts.append(
                f"Decision requires REVIEW from {len(self.review_reasons)} policies:"
            )
            for reason in self.review_reasons[:5]:
                parts.append(f"  - {reason}")

        self.decision_explanation = "\n".join(parts)

    @property
    def blocked_by(self) -> List[str]:
        """List of policy IDs that blocked execution."""
        blocked = []
        for outcome in self.outcomes:
            if outcome.is_block or outcome.is_error:
                blocked.append(outcome.policy_id)
        return blocked

    @property
    def all_policy_ids(self) -> List[str]:
        return [o.policy_id for o in self.outcomes]

    @property
    def has_errors(self) -> bool:
        return self.policies_errored > 0

    @property
    def summary(self) -> str:
        """Short one-line summary."""
        return (
            f"Verdict={self.overall_verdict}, "
            f"Policies={self.policies_evaluated}, "
            f"Passed={self.policies_passed}, "
            f"Blocked={self.policies_blocked}, "
            f"Errors={self.policies_errored}"
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def get_blocking_outcomes(self) -> List[PolicyOutcome]:
        """Get only outcomes that blocked execution."""
        return [o for o in self.outcomes if o.is_block or o.is_error]

    def get_review_outcomes(self) -> List[PolicyOutcome]:
        """Get only outcomes that require review."""
        return [o for o in self.outcomes if o.is_review]

    def get_outcomes_by_classification(self, classification: str) -> List[PolicyOutcome]:
        return [o for o in self.outcomes if o.classification == classification]

    def get_outcome(self, policy_id: str) -> Optional[PolicyOutcome]:
        """Get a specific policy's outcome."""
        for o in self.outcomes:
            if o.policy_id == policy_id:
                return o
        return None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "overall_verdict": self.overall_verdict,
            "execution_allowed": self.execution_allowed,
            "review_required": self.review_required,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "aggregated_effects": (
                self.aggregated_effects.to_dict()
                if self.aggregated_effects
                else None
            ),
            "policies_evaluated": self.policies_evaluated,
            "policies_passed": self.policies_passed,
            "policies_blocked": self.policies_blocked,
            "policies_errored": self.policies_errored,
            "policies_skipped": self.policies_skipped,
            "total_evaluation_time_ms": self.total_evaluation_time_ms,
            "active_versions": self.active_versions,
            "decision_explanation": self.decision_explanation,
            "blocking_reasons": self.blocking_reasons,
            "review_reasons": self.review_reasons,
            "summary": self.summary,
            "blocked_by": self.blocked_by,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionedPolicyResult":
        result = cls(
            decision_id=data.get("decision_id", ""),
            request_id=data.get("request_id", ""),
            overall_verdict=data.get("overall_verdict", "ALLOW"),
            execution_allowed=data.get("execution_allowed", True),
            review_required=data.get("review_required", False),
            policies_evaluated=data.get("policies_evaluated", 0),
            policies_passed=data.get("policies_passed", 0),
            policies_blocked=data.get("policies_blocked", 0),
            policies_errored=data.get("policies_errored", 0),
            policies_skipped=data.get("policies_skipped", 0),
            total_evaluation_time_ms=data.get("total_evaluation_time_ms", 0.0),
            active_versions=data.get("active_versions", []),
            decision_explanation=data.get("decision_explanation", ""),
            blocking_reasons=data.get("blocking_reasons", []),
            review_reasons=data.get("review_reasons", []),
            metadata=data.get("metadata", {}),
        )
        for od in data.get("outcomes", []):
            result.outcomes.append(PolicyOutcome.from_dict(od))
        result._recompute()
        return result

    def __repr__(self) -> str:
        return (
            f"VersionedPolicyResult(verdict={self.overall_verdict}, "
            f"policies={self.policies_evaluated}, "
            f"allowed={self.execution_allowed})"
        )
