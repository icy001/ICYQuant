"""
Governance Engine — Centralized Decision Authorization
Controls the lifecycle: REQUEST → EVALUATE → DECIDE → AUDIT

Versioned policy evaluation is supported via GovernanceEngine.evaluate_with_versions()
which uses PolicyRegistry for active version resolution.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .decision_context import DecisionContext
from .decision_request import DecisionRequest
from .decision_result import DecisionResult
from .decision_status import DecisionStatus
from .decision_governance import DecisionGovernance
from .policy_engine import PolicyEngine
from .authority_engine import AuthorityEngine
from .governance_constraint import ConstraintResult
from .approval_engine import ApprovalEngine
from .decision_guard import DecisionGuard
from .decision_audit import DecisionAudit, AuditRecord
from .governance_event import GovernanceEvent, GovernanceEventType
from .governance_event_store import GovernanceEventStore


class GovernanceVerdict(Enum):
    ALLOW = auto()
    REVIEW = auto()
    REJECT = auto()
    BLOCKED = auto()
    OVERRIDDEN = auto()
    EXPIRED = auto()
    CANCELLED = auto()


@dataclass
class GovernanceEvaluation:
    """Aggregated result of a full governance evaluation."""

    request_id: str
    decision_id: str
    context: DecisionContext

    # Stage results
    policy_result: Optional[Dict[str, Any]] = None
    authority_result: Optional[Dict[str, Any]] = None
    constraint_results: List[ConstraintResult] = field(default_factory=list)

    # Approval
    approval_required: bool = False
    approval_result: Optional[Dict[str, Any]] = None

    # Final
    verdict: GovernanceVerdict = GovernanceVerdict.REJECT
    reason: str = ""
    allow_execution: bool = False

    # Audit
    audit_record: Optional[AuditRecord] = None
    timestamp: float = field(default_factory=time.time)


class GovernanceEngine:
    """
    Central governance engine that routes every significant decision through:
      Policy → Authority → Constraint → Approval → Guard → Audit
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        authority_engine: Optional[AuthorityEngine] = None,
        approval_engine: Optional[ApprovalEngine] = None,
        decision_guard: Optional[DecisionGuard] = None,
        auditor: Optional[DecisionAudit] = None,
        event_store: Optional[GovernanceEventStore] = None,
    ):
        self._policy_engine = policy_engine or PolicyEngine()
        self._authority_engine = authority_engine or AuthorityEngine()
        self._approval_engine = approval_engine or ApprovalEngine()
        self._decision_guard = decision_guard or DecisionGuard()
        self._auditor = auditor or DecisionAudit()
        self._event_store = event_store or GovernanceEventStore()

        self._decision_governance = DecisionGovernance()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> GovernanceEvaluation:
        """Run the full governance pipeline and return an evaluation."""
        decision_id = self._generate_decision_id()
        self._emit(GovernanceEventType.GOVERNANCE_DECISION_REQUESTED, request, decision_id)

        evaluation = GovernanceEvaluation(
            request_id=request.request_id,
            decision_id=decision_id,
            context=context,
        )

        try:
            # Stage 1: Policy
            evaluation.policy_result = self._policy_engine.evaluate(request, context)
            self._emit(GovernanceEventType.GOVERNANCE_POLICY_EVALUATED, request, decision_id,
                       policy_result=evaluation.policy_result)

            if self._policy_is_blocking(evaluation.policy_result):
                evaluation.verdict = GovernanceVerdict.BLOCKED
                evaluation.reason = f"Policy breach: {self._policy_breach_summary(evaluation.policy_result)}"
                evaluation.allow_execution = False
                self._finalize(evaluation, request)
                return evaluation

            # Stage 2: Authority
            evaluation.authority_result = self._authority_engine.evaluate(request, context)
            self._emit(GovernanceEventType.GOVERNANCE_AUTHORITY_EVALUATED, request, decision_id,
                       authority_result=evaluation.authority_result)

            if self._authority_is_blocking(evaluation.authority_result):
                evaluation.verdict = GovernanceVerdict.BLOCKED
                evaluation.reason = f"Authority denied: {evaluation.authority_result.get('reason', 'unauthorized')}"
                evaluation.allow_execution = False
                self._finalize(evaluation, request)
                return evaluation

            # Stage 3: Constraints
            evaluation.constraint_results = self._decision_governance.evaluate_constraints(request, context)
            self._emit(GovernanceEventType.GOVERNANCE_CONSTRAINT_CHECKED, request, decision_id,
                       constraints=[r.to_dict() for r in evaluation.constraint_results])

            blocking_constraints = [c for c in evaluation.constraint_results if c.blocking]
            if blocking_constraints:
                evaluation.verdict = GovernanceVerdict.BLOCKED
                evaluation.reason = f"Constraints failed: {[c.name for c in blocking_constraints]}"
                evaluation.allow_execution = False
                self._finalize(evaluation, request)
                return evaluation

            # Stage 3b: Check if REVIEW is required (warnings from policy, authority, or constraints)
            if self._requires_review(evaluation):
                evaluation.verdict = GovernanceVerdict.REVIEW
                evaluation.approval_required = True
                self._emit(GovernanceEventType.GOVERNANCE_APPROVAL_REQUIRED, request, decision_id)

                # Try approval
                evaluation.approval_result = self._approval_engine.evaluate(request, context, evaluation)

                if evaluation.approval_result.get("approved", False):
                    evaluation.verdict = GovernanceVerdict.ALLOW
                    evaluation.allow_execution = True
                    self._emit(GovernanceEventType.GOVERNANCE_APPROVED, request, decision_id)
                else:
                    evaluation.verdict = GovernanceVerdict.REJECT
                    evaluation.reason = "Approval denied"
                    evaluation.allow_execution = False
                    self._emit(GovernanceEventType.GOVERNANCE_REJECTED, request, decision_id)
                    self._finalize(evaluation, request)
                    return evaluation

            else:
                # Stage 4: Decision Guard (final sanity check)
                guard_result = self._decision_guard.check(request, context, evaluation)
                if not guard_result.get("pass", False):
                    evaluation.verdict = GovernanceVerdict.BLOCKED
                    evaluation.reason = f"Decision guard blocked: {guard_result.get('reason', '')}"
                    evaluation.allow_execution = False
                    self._emit(GovernanceEventType.GOVERNANCE_BLOCKED, request, decision_id)
                    self._finalize(evaluation, request)
                    return evaluation

                evaluation.verdict = GovernanceVerdict.ALLOW
                evaluation.allow_execution = True

            self._finalize(evaluation, request)

        except Exception as exc:
            evaluation.verdict = GovernanceVerdict.BLOCKED
            evaluation.reason = f"Governance error: {exc}"
            evaluation.allow_execution = False
            self._finalize(evaluation, request)

        return evaluation

    def override_decision(
        self,
        request: DecisionRequest,
        context: DecisionContext,
        override_actor: str,
        override_reason: str,
        new_verdict: GovernanceVerdict,
    ) -> GovernanceEvaluation:
        """Create an explicit override (always audited)."""
        evaluation = self.evaluate(request, context)

        evaluation.verdict = new_verdict
        evaluation.allow_execution = (new_verdict == GovernanceVerdict.ALLOW)
        evaluation.reason = f"OVERRIDE by {override_actor}: {override_reason}"

        self._emit(
            GovernanceEventType.GOVERNANCE_OVERRIDE,
            request,
            evaluation.decision_id,
            override_actor=override_actor,
            override_reason=override_reason,
            original_verdict="BLOCKED",
            new_verdict=new_verdict.name,
        )

        audit = AuditRecord(
            decision_id=evaluation.decision_id,
            request_id=request.request_id,
            actor=override_actor,
            decision_type=request.decision_type,
            verdict=evaluation.verdict.name,
            reason=evaluation.reason,
            override=True,
            override_reason=override_reason,
            context_snapshot=context.to_dict(),
            timestamp=time.time(),
        )
        self._auditor.record(audit)
        evaluation.audit_record = audit

        return evaluation

    # ------------------------------------------------------------------
    # Versioned policy evaluation
    # ------------------------------------------------------------------

    def evaluate_with_versions(
        self, request: DecisionRequest, context: DecisionContext
    ) -> "VersionedPolicyResult":
        """
        Evaluate using versioned policies from the PolicyRegistry.

        This is the version-aware evaluation path that leverages:
          - PolicyRegistry for active version resolution
          - PolicyVersion for content integrity and lifecycle tracking
          - VersionedPolicyResult for full traceability

        Returns a VersionedPolicyResult with per-policy outcomes and explanations.
        """
        from .policy_result import VersionedPolicyResult

        if not self._policy_engine.has_registry:
            # Fall back to non-versioned evaluation
            legacy_result = self.evaluate(request, context)
            vr = VersionedPolicyResult(
                decision_id=legacy_result.decision_id,
                request_id=request.request_id,
                overall_verdict=legacy_result.verdict.name if legacy_result.verdict else "ALLOW",
                execution_allowed=legacy_result.allow_execution,
                total_evaluation_time_ms=0.0,
            )
            return vr

        return self._policy_engine.evaluate_versioned(request, context)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_decision_id() -> str:
        return f"GOV-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:8]}"

    def _emit(self, event_type: GovernanceEventType, request: DecisionRequest,
              decision_id: str, **extra) -> None:
        event = GovernanceEvent(
            event_type=event_type,
            decision_id=decision_id,
            request_id=request.request_id,
            actor=request.actor,
            decision_type=request.decision_type,
            payload=extra,
        )
        self._event_store.append(event)

    @staticmethod
    def _policy_is_blocking(policy_result: Optional[Dict[str, Any]]) -> bool:
        if not policy_result:
            return False
        return policy_result.get("blocking", False)

    @staticmethod
    def _policy_breach_summary(policy_result: Dict[str, Any]) -> str:
        breaches = policy_result.get("breaches", [])
        if not breaches:
            return "unknown"
        return "; ".join(b.get("description", str(b)) for b in breaches[:3])

    @staticmethod
    def _authority_is_blocking(authority_result: Optional[Dict[str, Any]]) -> bool:
        if not authority_result:
            return False
        return not authority_result.get("authorized", True)

    @staticmethod
    def _requires_review(evaluation: GovernanceEvaluation) -> bool:
        """Check whether any stage flagged review."""
        if evaluation.policy_result and evaluation.policy_result.get("review_required", False):
            return True
        if evaluation.authority_result and evaluation.authority_result.get("review_required", False):
            return True
        for c in evaluation.constraint_results:
            if c.review_required:
                return True
        return False

    def _finalize(self, evaluation: GovernanceEvaluation, request: DecisionRequest) -> None:
        audit = AuditRecord(
            decision_id=evaluation.decision_id,
            request_id=request.request_id,
            actor=request.actor,
            decision_type=request.decision_type,
            verdict=evaluation.verdict.name,
            reason=evaluation.reason,
            policy_result=evaluation.policy_result,
            authority_result=evaluation.authority_result,
            constraint_results=[c.to_dict() for c in evaluation.constraint_results],
            approval_result=evaluation.approval_result,
            context_snapshot=evaluation.context.to_dict(),
            timestamp=evaluation.timestamp,
        )
        self._auditor.record(audit)
        evaluation.audit_record = audit

        if evaluation.allow_execution:
            self._emit(GovernanceEventType.GOVERNANCE_EXECUTED, request, evaluation.decision_id)
